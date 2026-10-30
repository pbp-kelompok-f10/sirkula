import logging
from urllib.parse import urlencode
from uuid import uuid4

from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods
from django.views.decorators.vary import vary_on_cookie

from .demo_data import DEMO_RECOMMENDATIONS
from .forms import ChatMessageForm, MixAndMatchPromptForm
from .models import Conversation
from .services import ConversationConflict, conversation_history, get_landing_content, send_message, start_conversation
from .wardrobe_context import WardrobeChanged, WardrobeUnavailable, prepare_results_for_display

logger = logging.getLogger(__name__)


def _category(request):
    source = request.POST if request.method == "POST" else request.GET
    value = source.get("category", "")
    if not (0 < len(value) <= 10 and value.isascii() and value.isdigit() and int(value) > 0):
        return ""
    return value


def _url(name, category, **kwargs):
    url = reverse(name, kwargs=kwargs)
    return url + "?" + urlencode({"category": category}) if category else url


def _navigation(request):
    category = _category(request)
    return {"return_category": category, "wardrobe_url": _url("wardrobe:index", category), "new_chat_url": _url("outfits:index", category) + "#mix-prompt"}


def _landing_context(request, form):
    content = get_landing_content(user=request.user)
    for card in content["recommendations"]:
        card["request_key"] = uuid4()
        card["prompt"] = f"Tolong buatkan outfit dengan {card['title'].lower()}."
    return {**content, **_navigation(request), "prompt_form": form}


@never_cache
@vary_on_cookie
@require_http_methods(["GET", "HEAD", "POST"])
def index(request):
    data = request.POST.copy() if request.method == "POST" else None
    if data is not None and data.get("recommendation"):
        card = next((entry for entry in DEMO_RECOMMENDATIONS if entry["id"] == data["recommendation"]), None)
        if card:
            data["prompt"] = f"Tolong buatkan outfit dengan {card['title'].lower()}."
    form = MixAndMatchPromptForm(data, initial={"request_key": uuid4()})
    status = 200
    if request.method == "POST":
        valid = form.is_valid()
        if not request.user.is_authenticated:
            form.add_error(None, "Silakan login untuk memulai percakapan.")
            status = 403
        elif not valid:
            status = 400
        else:
            try:
                conversation = start_conversation(
                    user=request.user, prompt=form.cleaned_data["prompt"], key=form.cleaned_data["request_key"],
                    recommendation=form.cleaned_data["recommendation"],
                )
            except WardrobeUnavailable as error:
                form.add_error(None, str(error))
                status = 400
            except (ConversationConflict, WardrobeChanged) as error:
                form.add_error(None, str(error))
                status = 409
            except Exception:
                logger.exception("Gagal memulai percakapan Outfits untuk user_id=%s", request.user.pk)
                form.add_error(None, "Percakapan belum dapat disimpan. Silakan kirim kembali.")
                status = 500
            else:
                return redirect(_url("outfits:conversation", _category(request), conversation_id=conversation.pk))
    return render(request, "outfits/index.html", _landing_context(request, form), status=status)


def _conversation_context(request, conversation, form):
    return {
        **_navigation(request), "conversation": conversation,
        "chat_messages": conversation.messages.all(), "history": conversation_history(request.user),
        "chat_form": form, "result": prepare_results_for_display([conversation.result], request.user)[0],
    }


@never_cache
@vary_on_cookie
@require_http_methods(["GET", "HEAD", "POST"])
def conversation(request, conversation_id):
    if not request.user.is_authenticated:
        raise Http404("Percakapan tidak ditemukan.")
    current = get_object_or_404(Conversation, pk=conversation_id, owner=request.user)
    form = ChatMessageForm(request.POST if request.method == "POST" else None, initial={"request_key": uuid4(), "version": current.version})
    status = 200
    if request.method == "POST":
        if not form.is_valid():
            status = 400
        else:
            try:
                current = send_message(
                    user=request.user, conversation_id=current.pk, prompt=form.cleaned_data["prompt"],
                    key=form.cleaned_data["request_key"], version=form.cleaned_data["version"],
                )
            except Http404:
                raise
            except WardrobeUnavailable as error:
                form.add_error(None, str(error))
                status = 400
            except (ConversationConflict, WardrobeChanged) as error:
                form.add_error(None, str(error))
                status = 409
            except Exception:
                logger.exception("Gagal menyimpan pesan Outfits untuk user_id=%s", request.user.pk)
                form.add_error(None, "Pesan belum dapat disimpan. Silakan kirim kembali dengan isian yang sama.")
                status = 500
            else:
                url = _url("outfits:conversation", _category(request), conversation_id=current.pk)
                if "application/json" in request.headers.get("Accept", ""):
                    return JsonResponse({"ok": True, "url": url})
                return redirect(url)
        if "application/json" in request.headers.get("Accept", ""):
            return JsonResponse({"ok": False, "errors": form.errors.get_json_data()}, status=status)
    return render(request, "outfits/conversation.html", _conversation_context(request, current, form), status=status)
