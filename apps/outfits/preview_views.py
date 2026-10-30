from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_http_methods
from django.views.decorators.vary import vary_on_cookie

from .api_client import WardrobeAPIError
from .models import Conversation
from .preview_service import enqueue_preview, read_preview_image, read_preview_status


def owned_conversation(request, conversation_id):
    if not request.user.is_authenticated:
        raise Http404("Percakapan tidak ditemukan.")
    conversation = get_object_or_404(Conversation, pk=conversation_id, owner=request.user)
    if request.GET.get("version") is not None and request.GET["version"] != str(conversation.version):
        raise Http404("Pasangan preview sudah berubah.")
    return conversation


@never_cache
@vary_on_cookie
@require_http_methods(["GET", "POST"])
def preview(request, conversation_id):
    conversation = owned_conversation(request, conversation_id)
    try:
        data = enqueue_preview(request.user, conversation) if request.method == "POST" else read_preview_status(request.user, conversation)
    except Http404:
        return JsonResponse({"ok": True, "preview_status": "stale", "preview_url": None})
    except WardrobeAPIError as error:
        status = 403 if error.code == "preview_disabled" else 429 if error.code == "preview_limit" else 503
        return JsonResponse({"ok": False, "detail": str(error)}, status=status)
    data["preview_url"] = reverse("outfits:preview_image", kwargs={"conversation_id": conversation.pk}) + f"?version={conversation.version}" if data["preview_status"] == "ready" else None
    # Internal API job IDs/URLs never determine browser access.
    data.pop("preview_id", None)
    return JsonResponse({"ok": True, **data})


@never_cache
@vary_on_cookie
@require_GET
def preview_image(request, conversation_id):
    conversation = owned_conversation(request, conversation_id)
    try:
        raw = read_preview_image(request.user, conversation)
    except WardrobeAPIError:
        return HttpResponse(status=503)
    response = HttpResponse(raw, content_type="image/png")
    response["X-Content-Type-Options"] = "nosniff"
    response["Cross-Origin-Resource-Policy"] = "same-origin"
    return response
