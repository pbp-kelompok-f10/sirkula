from copy import deepcopy

from django.contrib.auth import get_user_model
from django.conf import settings
from django.urls import reverse
from django.db import transaction
from django.http import Http404

from .demo_data import DEMO_RECOMMENDATIONS
from .models import Conversation, Message
from .providers import get_stylist_provider
from .preview_service import start_preview_after_match
from .wardrobe_context import (
    WardrobeUnavailable, build_result, get_wardrobe_context,
    lock_and_validate_selection, prepare_results_for_display,
)


class ConversationConflict(Exception):
    pass


def get_landing_content(*, user=None):
    history = list(conversation_history(user)) if user is not None and user.is_authenticated else []
    rendered = prepare_results_for_display([entry.result for entry in history], user) if history else []
    for entry, result in zip(history, rendered):
        entry.result = result
    recommendations = deepcopy(list(DEMO_RECOMMENDATIONS))
    if settings.OUTFITS_PROVIDER == "api":
        from .sync import category_type
        wardrobe = get_wardrobe_context(user) if user is not None and user.is_authenticated else ()
        eligible = [item for item in wardrobe if category_type(item) and item["photos"]]
        recommendations = []
        if eligible:
            for index in range(4):
                item = eligible[index % len(eligible)]
                mode = "best" if index % 2 == 0 else "random"
                recommendations.append({
                    "id": DEMO_RECOMMENDATIONS[index]["id"], "title": mode.title(), "prompt": mode,
                    "image": {"kind": "url", "url": reverse("wardrobe:item_photo", kwargs={"photo_id": item["photos"][0]["id"]})},
                })
    return {
        "mode": settings.OUTFITS_PROVIDER,
        "recommendations": recommendations,
        "history": history,
    }


def conversation_history(user):
    return Conversation.objects.filter(owner=user).only("id", "title", "result", "updated_at")


def _validated_reply(*, user, prompt, history, key, recommendation=""):
    wardrobe = get_wardrobe_context(user)
    if settings.OUTFITS_PROVIDER == "demo" and not any(item["photos"] for item in wardrobe):
        raise WardrobeUnavailable("Tambahkan pakaian aktif dengan foto di Wardrobe terlebih dahulu.")
    provider = get_stylist_provider()
    if hasattr(provider, "reply_for_user"):
        return provider.reply_for_user(user=user, prompt=prompt, history=history,
                                       wardrobe=wardrobe, key=key, recommendation=recommendation)
    reply = provider.reply(
        prompt=prompt, history=history, wardrobe=deepcopy(wardrobe), recommendation=recommendation,
    )
    if not isinstance(reply.text, str) or not 1 <= len(reply.text.strip()) <= 4000:
        raise ValueError("Invalid assistant message")
    if not isinstance(reply.title, str) or not 1 <= len(reply.title.strip()) <= 100:
        raise ValueError("Invalid conversation title")
    return reply, build_result(reply.result, wardrobe)


def _write_pair(conversation, prompt, reply_text, key, version, *, status=False):
    Message.objects.bulk_create([
        Message(conversation=conversation, role=Message.Role.USER, content=prompt, sequence=2 * version - 1, request_key=key),
        Message(conversation=conversation, role=Message.Role.STATUS if status else Message.Role.ASSISTANT, content=reply_text, sequence=2 * version, request_key=key),
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
    reply, result = _validated_reply(user=user, prompt=prompt, history=(), key=key, recommendation=recommendation)
    with transaction.atomic():
        # Serialize creation keys for this owner; inference happens before the lock.
        get_user_model().objects.select_for_update().get(pk=user.pk)
        existing = _existing_start(user, key, prompt, recommendation)
        if existing:
            return existing
        lock_and_validate_selection(user, result)
        conversation = Conversation.objects.create(
            owner=user, creation_key=key, initial_recommendation=recommendation,
            title=reply.title.strip(), result=result,
        )
        _write_pair(conversation, prompt, reply.text, key, 1, status="api" in result)
    return start_preview_after_match(user, conversation)


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
    reply, result = _validated_reply(user=user, prompt=prompt, history=tuple(reversed(history)), key=key)
    with transaction.atomic():
        conversation = Conversation.objects.select_for_update().get(pk=conversation_id, owner=user)
        if _existing_turn(conversation, key, prompt):
            return conversation
        if conversation.version != version:
            raise ConversationConflict("Percakapan berubah di tab lain. Buka ulang percakapan dari menu riwayat sebelum melanjutkan.")
        lock_and_validate_selection(user, result)
        _write_pair(conversation, prompt, reply.text, key, version + 1, status="api" in result)
        conversation.version += 1
        conversation.result = result
        conversation.save(update_fields=["version", "result", "updated_at"])
    return start_preview_after_match(user, conversation)
