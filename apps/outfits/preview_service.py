"""Explicit, budget-gated preview creation; status/image reads never enqueue."""
import hashlib
import json

from django.conf import settings
from django.db import transaction
from django.db.models import F
from django.http import Http404

from .api_client import WardrobeAPIClient, WardrobeAPIError, identifier
from .models import OutfitPreviewAttempt, OutfitUserPreviewBudget, WardrobeAPIAccount, WardrobeAPIMapping
from .sync import account_lease, category_type

PREVIEW_LABEL = "Ilustrasi AI; detail pakaian dan ukuran dapat berbeda."
STATUSES = {"queued", "running", "ready", "stale", "failed_or_unknown"}


def pair_context(user, conversation):
    try:
        api = conversation.result["api"]
        account = WardrobeAPIAccount.objects.get(owner=user)
        pieces = {piece["item_id"]: piece for piece in conversation.result["pieces"]}
        ids = []
        for name, category in (("top", "baju"), ("bottom", "celana")):
            reference = api[name]
            mapping = account.mappings.select_related("item__category").get(
                item_id=reference["local_id"], api_id=reference["api_id"], revision=reference["revision"],
                item__owner=user, item__status="active", upload_pending=False,
            )
            item = mapping.item
            snapshot = pieces[item.pk]
            if (item.updated_at.isoformat() != snapshot["item_version"]
                    or category_type({"category": {"name": item.category.name} if item.category_id else None}) != category
                    or not item.images.filter(pk=snapshot["image"]["photo_id"]).exists()):
                raise Http404("Pasangan preview sudah berubah.")
            photo = item.images.get(pk=snapshot["image"]["photo_id"])
            if not photo.image.storage.exists(photo.image.name):
                raise Http404("Foto tidak tersedia.")
            ids.append(identifier(reference["api_id"]))
        pair_key = hashlib.sha256(json.dumps([api["top"], api["bottom"]], sort_keys=True).encode()).hexdigest()
        return account, ids, pair_key
    except (KeyError, TypeError, WardrobeAPIAccount.DoesNotExist, ValueError):
        raise Http404("Preview tidak tersedia.") from None
    except WardrobeAPIMapping.DoesNotExist:
        raise Http404("Pasangan preview sudah berubah.") from None


def _validated_status(data, ids):
    if (not isinstance(data, dict) or data.get("baju_id") != ids[0] or data.get("celana_id") != ids[1]
            or data.get("preview_status") not in STATUSES):
        raise WardrobeAPIError(code="invalid_response")
    return {"preview_id": identifier(data.get("preview_id"), preview=True),
            "preview_status": data["preview_status"], "preview_label": PREVIEW_LABEL}


def _status(user, conversation, client, account, ids, pair_key):
    if account.endpoint != client.base_url:
        raise WardrobeAPIError(code="configuration")
    attempt = OutfitPreviewAttempt.objects.filter(account=account, pair_key=pair_key).first()
    key = conversation.result["api"].get("preview_id") or (attempt.api_preview_id if attempt else "")
    if not key and attempt:
        if conversation.result["api"].get("preview_start_status") == "disabled":
            return {"preview_status": "disabled", "preview_label": PREVIEW_LABEL}
        # A timed-out enqueue may have been accepted. Matching manual is free and
        # reveals an existing job; it must never be replaced with another enqueue.
        data = client.match(account.api_owner, {"mode": "manual", "baju_id": ids[0], "celana_id": ids[1]})
        rows = data.get("results", [])
        if not isinstance(rows, list) or (rows and not isinstance(rows[0], dict)):
            raise WardrobeAPIError(code="invalid_response")
        if len(rows) == 1 and rows[0].get("baju_id") == ids[0] and rows[0].get("celana_id") == ids[1]:
            key = rows[0].get("preview_id", "")
        if not key:
            return {"preview_status": "failed_or_unknown", "preview_label": PREVIEW_LABEL}
    if not key:
        state = conversation.result["api"].get("preview_start_status", "not_generated")
        return {"preview_status": state, "preview_label": PREVIEW_LABEL}
    data = client.preview_status(account.api_owner, identifier(key, preview=True))
    if data is None:
        return {"preview_status": "stale", "preview_label": PREVIEW_LABEL}
    result = _validated_status(data, ids)
    if attempt:
        attempt.api_preview_id = result["preview_id"]
        attempt.status = result["preview_status"]
        attempt.save(update_fields=["api_preview_id", "status"])
    return result


def read_preview_status(user, conversation):
    account, ids, pair_key = pair_context(user, conversation)
    return _status(user, conversation, WardrobeAPIClient(), account, ids, pair_key)


def enqueue_preview(user, conversation):
    if not settings.OUTFITS_PREVIEW_ENABLED or settings.OUTFITS_PREVIEW_MAX_REQUESTS <= 0:
        raise WardrobeAPIError("Generate preview dinonaktifkan sampai batas atau kuota disetujui.", code="preview_disabled")
    client = WardrobeAPIClient()
    with account_lease(user, client) as (account, renew):
        current, ids, pair_key = pair_context(user, conversation)
        existing = OutfitPreviewAttempt.objects.filter(account=account, pair_key=pair_key).first()
        if existing or conversation.result["api"].get("preview_id"):
            return _status(user, conversation, client, account, ids, pair_key)
        with transaction.atomic():
            budget, _ = OutfitUserPreviewBudget.objects.get_or_create(owner=user)
            budget = OutfitUserPreviewBudget.objects.select_for_update().get(pk=budget.pk)
            if budget.attempts >= min(20, settings.OUTFITS_PREVIEW_MAX_REQUESTS):
                raise WardrobeAPIError("Kuota preview pengguna sudah habis.", code="preview_limit")
            budget.attempts += 1
            budget.save(update_fields=["attempts"])
            attempt = OutfitPreviewAttempt.objects.create(account=account, pair_key=pair_key)
        renew()
        # An uncertain POST consumes the attempt. Only status reconciliation can retry.
        try:
            data = client.preview(account.api_owner, *ids)
        except WardrobeAPIError as error:
            if error.code == "preview_disabled":
                # Definitive rejection: no job was accepted, unlike a timeout.
                # Do not permanently poison this pair or consume local quota.
                with transaction.atomic():
                    attempt.delete()
                    OutfitUserPreviewBudget.objects.filter(owner=user, attempts__gt=0).update(attempts=F("attempts") - 1)
            raise
        result = _validated_status(data, ids)
        attempt.api_preview_id = result["preview_id"]
        attempt.status = result["preview_status"]
        attempt.save(update_fields=["api_preview_id", "status"])
        return result


def read_preview_image(user, conversation):
    account, ids, pair_key = pair_context(user, conversation)
    client = WardrobeAPIClient()
    data = _status(user, conversation, client, account, ids, pair_key)
    if data["preview_status"] != "ready":
        raise Http404("Preview belum tersedia.")
    return client.preview_image(account.api_owner, data["preview_id"])


def start_preview_after_match(user, conversation):
    """Called only for a newly committed API match; replay/GET must never enqueue."""
    if "api" not in conversation.result:
        return conversation
    try:
        data = enqueue_preview(user, conversation)
        state = data["preview_status"]
    except Http404:
        state = "stale"
    except WardrobeAPIError as error:
        state = {"preview_disabled": "disabled", "preview_limit": "limit_reached"}.get(error.code, "failed_or_unknown")
    result = dict(conversation.result)
    result["api"] = {**result["api"], "preview_start_status": state}
    # Another tab may have advanced the conversation while the preview was queued.
    from .models import Conversation
    Conversation.objects.filter(pk=conversation.pk, owner=user, version=conversation.version).update(result=result)
    conversation.result = result
    return conversation
