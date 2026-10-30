from copy import deepcopy
from urllib.parse import urlsplit

from django.contrib.auth import get_user_model
from django.db import transaction
from django.http import Http404

from .demo_data import DEMO_RECOMMENDATIONS
from .models import Conversation, Message
from .providers import get_stylist_provider


class ConversationConflict(Exception):
    pass


def get_landing_content(*, user=None):
    history = list(conversation_history(user)) if user is not None and user.is_authenticated else []
    return {
        "mode": "demo",
        "recommendations": deepcopy(list(DEMO_RECOMMENDATIONS)),
        "history": history,
    }


def conversation_history(user):
    return Conversation.objects.filter(owner=user).only("id", "title", "result", "updated_at")


def _validate_image(image):
    if not isinstance(image, dict):
        raise ValueError("Invalid provider image")
    if image.get("kind") == "reference":
        if not image.get("source", "").startswith("outfits/img/") or ".." in image["source"]:
            raise ValueError("Invalid reference asset")
        coordinates = image.get("viewbox", "").split()
        if len(coordinates) != 4 or any(not value.isdigit() for value in coordinates):
            raise ValueError("Invalid image viewport")
        if any(not isinstance(image.get(key), int) or image[key] <= 0 for key in ("width", "height")):
            raise ValueError("Invalid image size")
    elif image.get("kind") == "url":
        url = image.get("url", "")
        parts = urlsplit(url)
        if parts.scheme or parts.netloc or not url.startswith(("/outfits/images/", "/wardrobe/photos/")) or ".." in url:
            raise ValueError("Provider images must use an authenticated local endpoint")
    else:
        raise ValueError("Unknown provider image type")


def _validated_reply(*, prompt, history, recommendation=""):
    reply = get_stylist_provider().reply(prompt=prompt, history=history, recommendation=recommendation)
    if not isinstance(reply.text, str) or not 1 <= len(reply.text.strip()) <= 4000:
        raise ValueError("Invalid assistant message")
    if not isinstance(reply.title, str) or not 1 <= len(reply.title.strip()) <= 100:
        raise ValueError("Invalid conversation title")
    result = deepcopy(reply.result)
    if not isinstance(result, dict) or result.get("mode") not in ("demo", "ai"):
        raise ValueError("Invalid provider result")
    _validate_image(result.get("preview"))
    pieces = result.get("pieces")
    if not isinstance(pieces, list) or not 1 <= len(pieces) <= 5:
        raise ValueError("Invalid outfit pieces")
    for piece in pieces:
        if not isinstance(piece.get("name"), str) or not 1 <= len(piece["name"]) <= 100:
            raise ValueError("Invalid outfit piece")
        _validate_image(piece.get("image"))
    return reply, result


def _write_pair(conversation, prompt, reply_text, key, version):
    Message.objects.bulk_create([
        Message(conversation=conversation, role=Message.Role.USER, content=prompt, sequence=2 * version - 1, request_key=key),
        Message(conversation=conversation, role=Message.Role.ASSISTANT, content=reply_text, sequence=2 * version, request_key=key),
    ])


def _existing_start(user, key, prompt, recommendation):
    conversation = Conversation.objects.filter(owner=user, creation_key=key).first()
    if conversation:
        initial = conversation.messages.filter(sequence=1).first()
        if initial is None or initial.content != prompt or conversation.initial_recommendation != recommendation:
            raise ConversationConflict("Permintaan ini sudah dipakai. Buka ulang halaman untuk memulai percakapan lain.")
    return conversation


def start_conversation(*, user, prompt, key, recommendation=""):
    existing = _existing_start(user, key, prompt, recommendation)
    if existing:
        return existing
    reply, result = _validated_reply(prompt=prompt, history=(), recommendation=recommendation)
    with transaction.atomic():
        # Serialize creation keys for this owner; inference happens before the lock.
        get_user_model().objects.select_for_update().get(pk=user.pk)
        existing = _existing_start(user, key, prompt, recommendation)
        if existing:
            return existing
        conversation = Conversation.objects.create(
            owner=user, creation_key=key, initial_recommendation=recommendation,
            title=reply.title.strip(), result=result,
        )
        _write_pair(conversation, prompt, reply.text, key, 1)
    return conversation


def _existing_turn(conversation, key, prompt):
    message = conversation.messages.filter(request_key=key, role=Message.Role.USER).first()
    if message and message.content != prompt:
        raise ConversationConflict("Permintaan ini sudah dipakai untuk pesan lain. Buka ulang percakapan dari riwayat.")
    return message is not None


def send_message(*, user, conversation_id, prompt, key, version):
    conversation = Conversation.objects.filter(pk=conversation_id, owner=user).first()
    if conversation is None:
        raise Http404("Percakapan tidak ditemukan.")
    if _existing_turn(conversation, key, prompt):
        return conversation
    if conversation.version != version:
        raise ConversationConflict("Percakapan berubah di tab lain. Buka ulang percakapan dari menu riwayat sebelum melanjutkan.")
    history = list(conversation.messages.order_by("-sequence").values("role", "content")[:20])
    reply, result = _validated_reply(prompt=prompt, history=tuple(reversed(history)))
    with transaction.atomic():
        conversation = Conversation.objects.select_for_update().get(pk=conversation_id, owner=user)
        if _existing_turn(conversation, key, prompt):
            return conversation
        if conversation.version != version:
            raise ConversationConflict("Percakapan berubah di tab lain. Buka ulang percakapan dari menu riwayat sebelum melanjutkan.")
        _write_pair(conversation, prompt, reply.text, key, version + 1)
        conversation.version += 1
        conversation.result = result
        conversation.save(update_fields=["version", "result", "updated_at"])
    return conversation
