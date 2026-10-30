"""Owned wardrobe snapshots and private-photo presentation for Outfits."""
from copy import deepcopy
from urllib.parse import urlsplit

from django.db.models import Prefetch
from django.urls import Resolver404, resolve, reverse

from apps.wardrobe.models import WardrobeItem, WardrobeItemImage


class WardrobeUnavailable(Exception):
    pass


class WardrobeChanged(Exception):
    pass


def _file_exists(photo):
    return bool(photo.image) and photo.image.storage.exists(photo.image.name)


def get_wardrobe_context(user):
    items = WardrobeItem.objects.filter(owner=user, status=WardrobeItem.Status.ACTIVE).select_related("category").prefetch_related(
        Prefetch("images", queryset=WardrobeItemImage.objects.order_by("position", "pk"))
    ).order_by("pk")
    return tuple({
        "id": item.pk,
        "name": item.name,
        "category": {"id": item.category_id, "name": item.category.name} if item.category_id else None,
        "updated_at": item.updated_at.isoformat(),
        "photos": tuple({"id": photo.pk, "position": photo.position} for photo in item.images.all() if _file_exists(photo)),
    } for item in items)


def build_result(provider_result, wardrobe):
    if not isinstance(provider_result, dict) or set(provider_result) != {"mode", "item_ids"}:
        raise ValueError("Invalid wardrobe selection")
    ids = provider_result["item_ids"]
    if provider_result["mode"] not in ("demo", "ai") or not isinstance(ids, list) or not 1 <= len(ids) <= 5:
        raise ValueError("Invalid wardrobe selection")
    if any(type(item_id) is not int for item_id in ids) or len(set(ids)) != len(ids):
        raise ValueError("Invalid wardrobe selection IDs")
    allowed = {item["id"]: item for item in wardrobe}
    pieces = []
    for item_id in ids:
        item = allowed.get(item_id)
        if item is None or not item["photos"]:
            raise ValueError("Provider selected unavailable clothing")
        pieces.append({
            "item_id": item_id,
            "name": item["name"],
            "category": deepcopy(item["category"]),
            "item_version": item["updated_at"],
            "image": {"kind": "wardrobe", "item_id": item_id, "photo_id": item["photos"][0]["id"]},
        })
    return {"mode": provider_result["mode"], "source": "wardrobe", "preview": deepcopy(pieces[0]["image"]), "pieces": pieces}


def lock_and_validate_selection(user, result):
    pieces = result["pieces"]
    items = {item.pk: item for item in WardrobeItem.objects.select_for_update().filter(
        pk__in=[piece["item_id"] for piece in pieces], owner=user, status=WardrobeItem.Status.ACTIVE,
    ).order_by("pk")}
    photos = {photo.pk: photo for photo in WardrobeItemImage.objects.select_for_update().filter(
        pk__in=[piece["image"]["photo_id"] for piece in pieces], item_id__in=items,
    ).order_by("pk")}
    for piece in pieces:
        item = items.get(piece["item_id"])
        photo = photos.get(piece["image"]["photo_id"])
        if item is None or item.updated_at.isoformat() != piece["item_version"] or photo is None or photo.item_id != item.pk or not _file_exists(photo):
            raise WardrobeChanged("Pakaian atau fotonya berubah. Periksa Wardrobe lalu kirim kembali.")


def _photo_ref(image):
    if not isinstance(image, dict):
        return None
    if image.get("kind") == "wardrobe":
        if type(image.get("photo_id")) is int and type(image.get("item_id")) is int:
            return image["photo_id"], image["item_id"]
    if image.get("kind") == "url":
        parts = urlsplit(image.get("url", ""))
        if parts.scheme or parts.netloc:
            return None
        try:
            match = resolve(parts.path)
        except Resolver404:
            return None
        if match.view_name == "wardrobe:item_photo":
            return match.kwargs["photo_id"], None
    return None


def _legacy_reference(image):
    if not isinstance(image, dict) or image.get("kind") not in (None, "reference"):
        return False
    source = image.get("source", "")
    coordinates = image.get("viewbox", "").split()
    return (source.startswith("outfits/img/") and ".." not in source
            and len(coordinates) == 4 and all(value.isdigit() for value in coordinates)
            and all(type(image.get(key)) is int and image[key] > 0 for key in ("width", "height")))


def prepare_results_for_display(results, user):
    """Resolve references afresh; never persist URLs or rewrite old history."""
    prepared = deepcopy(results)
    images = []
    for result in prepared:
        images.append((result, "preview"))
        images.extend((piece, "image") for piece in result.get("pieces", []))
    refs = {ref for container, key in images if (ref := _photo_ref(container.get(key))) is not None}
    photos = {photo.pk: photo for photo in WardrobeItemImage.objects.select_related("item").filter(
        pk__in=[photo_id for photo_id, _ in refs], item__owner=user, item__status=WardrobeItem.Status.ACTIVE,
    )} if refs else {}
    exists = {}
    for container, key in images:
        image = container.get(key)
        ref = _photo_ref(image)
        if ref is not None:
            photo_id, item_id = ref
            photo = photos.get(photo_id)
            if photo is not None and (item_id is None or photo.item_id == item_id):
                if photo_id not in exists:
                    exists[photo_id] = _file_exists(photo)
                if exists[photo_id]:
                    container[key] = {"kind": "url", "url": reverse("wardrobe:item_photo", kwargs={"photo_id": photo_id})}
                    continue
        elif _legacy_reference(image):
            continue
        container[key] = {"kind": "unavailable"}
    return prepared
