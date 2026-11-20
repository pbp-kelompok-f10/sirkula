from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .api_client import WardrobeAPIError
from .api_serializers import ConversationSerializer, MessageInputSerializer, StartSerializer
from .models import Conversation
from .preview_service import enqueue_preview, read_preview_image, read_preview_status
from .services import ConversationConflict, send_message, start_conversation
from .wardrobe_context import WardrobeChanged, WardrobeUnavailable


def service_error(error):
    if isinstance(error, WardrobeAPIError):
        code = 403 if error.code == "preview_disabled" else 429 if error.code == "preview_limit" else 409 if error.code in {"busy", "changed", "upload_unknown", "catalog_unknown"} else 503
        return Response({"detail": str(error), "code": error.code}, status=code)
    if isinstance(error, WardrobeUnavailable):
        return Response({"detail": str(error)}, status=400)
    return Response({"detail": str(error)}, status=409)


def owned(request, pk):
    return get_object_or_404(Conversation, pk=pk, owner=request.user)


def representation(request, conversation):
    return ConversationSerializer(conversation, context={"request": request}).data


@method_decorator(never_cache, name="dispatch")
class Conversations(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        conversations = Conversation.objects.filter(owner=request.user).prefetch_related("messages")
        return Response(ConversationSerializer(conversations, many=True, context={"request": request}).data)

    def post(self, request):
        serializer = StartSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            conversation = start_conversation(user=request.user, prompt=data["prompt"], key=data["request_key"], recommendation=data["recommendation"])
        except (WardrobeAPIError, WardrobeUnavailable, WardrobeChanged, ConversationConflict) as error:
            return service_error(error)
        return Response(representation(request, conversation), status=status.HTTP_201_CREATED)


@method_decorator(never_cache, name="dispatch")
class ConversationDetail(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, pk):
        return Response(representation(request, owned(request, pk)))


@method_decorator(never_cache, name="dispatch")
class ConversationMessages(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        owned(request, pk)
        serializer = MessageInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            conversation = send_message(user=request.user, conversation_id=pk, prompt=data["prompt"], key=data["request_key"], version=data["version"])
        except (WardrobeAPIError, WardrobeUnavailable, WardrobeChanged, ConversationConflict) as error:
            return service_error(error)
        return Response(representation(request, conversation))


@method_decorator(never_cache, name="dispatch")
class Preview(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def process(self, request, pk, create):
        conversation = owned(request, pk)
        if request.query_params.get("version") is not None and request.query_params["version"] != str(conversation.version):
            raise Http404
        try:
            data = enqueue_preview(request.user, conversation) if create else read_preview_status(request.user, conversation)
        except Http404:
            return Response({"preview_status": "stale", "preview_url": None})
        except WardrobeAPIError as error:
            return service_error(error)
        data.pop("preview_id", None)
        data["preview_url"] = request.build_absolute_uri(reverse("outfits_drf:preview_image", kwargs={"pk": pk}) + f"?version={conversation.version}") if data["preview_status"] == "ready" else None
        return Response(data)

    def get(self, request, pk):
        return self.process(request, pk, False)

    def post(self, request, pk):
        return self.process(request, pk, True)


@method_decorator(never_cache, name="dispatch")
class PreviewImage(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, pk):
        conversation = owned(request, pk)
        if request.query_params.get("version") is not None and request.query_params["version"] != str(conversation.version):
            raise Http404
        try:
            raw = read_preview_image(request.user, conversation)
        except WardrobeAPIError as error:
            return service_error(error)
        response = HttpResponse(raw, content_type="image/png")
        response["X-Content-Type-Options"] = "nosniff"
        response["Cross-Origin-Resource-Policy"] = "same-origin"
        return response
