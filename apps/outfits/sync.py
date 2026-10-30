"""Synchronize primary photos in an isolated per-user remote catalog."""
import hashlib
import io
import uuid
import warnings
from contextlib import contextmanager
from datetime import timedelta

from PIL import Image, ImageOps
from django.db.models import Q
from django.utils import timezone

from apps.wardrobe.models import WardrobeItemImage
from .api_client import WardrobeAPIError
from .models import WardrobeAPIAccount, WardrobeAPIMapping

CATEGORY_TYPES = {"kaos": "baju", "kemeja": "baju", "outer": "baju", "celana": "celana"}


def category_type(item):
    return CATEGORY_TYPES.get((item.get("category") or {}).get("name", "").strip().casefold())


def canonical_photo(raw):
    # Same normalization as core.clean_image in the supplied API contract.
    with warnings.catch_warnings():
        warnings.simplefilter("error", Image.DecompressionBombWarning)
        with Image.open(io.BytesIO(raw)) as source:
            if source.format not in {"JPEG", "PNG", "WEBP"} or source.width * source.height > 20_000_000:
                raise ValueError("Invalid photograph")
            source.load()
            rgba = ImageOps.exif_transpose(source).convert("RGBA")
            image = Image.new("RGBA", rgba.size, "white")
            image.alpha_composite(rgba)
            image = image.convert("RGB")
            image.thumbnail((1024, 1024))
            output = io.BytesIO()
            image.save(output, format="JPEG", quality=92)
            return output.getvalue()


@contextmanager
def account_lease(user, client):
    account, _ = WardrobeAPIAccount.objects.get_or_create(owner=user, defaults={"endpoint": client.base_url})
    if account.endpoint != client.base_url:
        raise WardrobeAPIError("Alamat API berubah. Pemetaan katalog perlu diperiksa administrator.", code="configuration")
    token = uuid.uuid4()
    def renew():
        if not WardrobeAPIAccount.objects.filter(pk=account.pk, lease_token=token).update(lease_until=timezone.now() + timedelta(seconds=180)):
            raise WardrobeAPIError("Sinkronisasi berubah. Silakan coba kembali.", code="busy")
    acquired = WardrobeAPIAccount.objects.filter(pk=account.pk).filter(
        Q(lease_until__isnull=True) | Q(lease_until__lt=timezone.now())
    ).update(lease_token=token, lease_until=timezone.now() + timedelta(seconds=180))
    if not acquired:
        raise WardrobeAPIError("Pakaian sedang disinkronkan. Tunggu sebentar lalu coba kembali.", code="busy")
    try:
        yield account, renew
    finally:
        WardrobeAPIAccount.objects.filter(pk=account.pk, lease_token=token).update(lease_token=None, lease_until=None)


def _photo_bytes(user, item):
    photo = WardrobeItemImage.objects.filter(
        pk=item["photos"][0]["id"], item_id=item["id"], item__owner=user, item__status="active",
    ).first()
    if photo is None:
        raise WardrobeAPIError("Foto pakaian berubah. Muat ulang Wardrobe.", code="changed")
    try:
        with photo.image.open("rb") as source:
            raw = source.read(5_000_001)
        if not raw or len(raw) > 5_000_000:
            raise ValueError("Invalid size")
        checksum = hashlib.sha256(canonical_photo(raw)).hexdigest()
    except (OSError, ValueError, Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise WardrobeAPIError("Foto tidak dapat diproses. Periksa foto di Wardrobe.", code="photo") from None
    return raw, checksum


def sync_wardrobe(user, wardrobe, account, client, renew):
    eligible = {item["id"]: item for item in wardrobe if category_type(item) and item["photos"]}
    renew()
    catalog = client.catalog(account.api_owner)
    mappings = list(account.mappings.all())
    claimed = {mapping.api_id for mapping in mappings if mapping.api_id}
    # POST creates a random API ID and has no idempotency key. Reconcile ambiguous
    # uploads by category AND normalized photo bytes; never blindly POST again.
    for mapping in mappings:
        if not mapping.upload_pending:
            continue
        candidates = []
        for key, remote in catalog.items():
            if key not in claimed and remote["category"] == mapping.category:
                renew()
                if hashlib.sha256(client.item_image(account.api_owner, key)).hexdigest() == mapping.checksum:
                    candidates.append(key)
        if len(candidates) != 1:
            raise WardrobeAPIError("Status upload sebelumnya belum dapat dipastikan. Coba lagi nanti; bila tetap terjadi, hubungi administrator.", code="upload_unknown")
        mapping.api_id = candidates[0]
        mapping.upload_pending = False
        mapping.revision = catalog[mapping.api_id]["revision"]
        mapping.save(update_fields=["api_id", "upload_pending", "revision"])
        claimed.add(mapping.api_id)

    for mapping in mappings:
        if mapping.item_id not in eligible:
            if mapping.api_id:
                renew()
                client.delete(account.api_owner, mapping.api_id)
                catalog.pop(mapping.api_id, None)
            mapping.delete()
    by_item = {mapping.item_id: mapping for mapping in account.mappings.all()}
    synced = []
    for item_id, item in eligible.items():
        renew()
        raw, checksum = _photo_bytes(user, item)
        category = category_type(item)
        photo_id = item["photos"][0]["id"]
        mapping = by_item.get(item_id)
        if mapping and mapping.api_id not in catalog:
            mapping.delete()
            mapping = None
        if mapping is None:
            mapping = WardrobeAPIMapping.objects.create(
                account=account, item_id=item_id, category=category, checksum=checksum,
                photo_id=photo_id, item_version=item["updated_at"], upload_pending=True,
            )
            api_id = client.put(account.api_owner, category, raw)
            mapping.api_id = api_id
            mapping.upload_pending = False
            mapping.save(update_fields=["api_id", "upload_pending"])
        elif mapping.checksum != checksum or mapping.category != category or mapping.photo_id != photo_id:
            client.put(account.api_owner, category, raw, mapping.api_id)
        mapping.category = category
        mapping.checksum = checksum
        mapping.photo_id = photo_id
        mapping.item_version = item["updated_at"]
        mapping.save(update_fields=["category", "checksum", "photo_id", "item_version"])
        synced.append({**item, "api_id": mapping.api_id, "api_category": category})
    renew()
    catalog = client.catalog(account.api_owner)
    for item in synced:
        remote = catalog.get(item["api_id"])
        if remote is None or remote["category"] != item["api_category"]:
            raise WardrobeAPIError(code="changed")
        WardrobeAPIMapping.objects.filter(account=account, item_id=item["id"]).update(revision=remote["revision"])
        item["api_revision"] = remote["revision"]
    # Unknown records must not be considered as candidates for this local wardrobe.
    if set(catalog) != {item["api_id"] for item in synced}:
        raise WardrobeAPIError("Katalog API memiliki data yang belum terpetakan. Perlu pemeriksaan administrator.", code="catalog_unknown")
    return tuple(synced)
