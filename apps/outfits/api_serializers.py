from django.urls import resolve, reverse

from rest_framework import serializers

from .models import Conversation, Message
from .wardrobe_context import prepare_results_for_display


class StartSerializer(serializers.Serializer):
    prompt = serializers.CharField(max_length=500, trim_whitespace=True)
    request_key = serializers.UUIDField()
    recommendation = serializers.ChoiceField(choices=["", "best", "random"], required=False, allow_blank=True, default="")


class MessageInputSerializer(serializers.Serializer):
    prompt = serializers.CharField(max_length=500, trim_whitespace=True)
    request_key = serializers.UUIDField()
    version = serializers.IntegerField(min_value=1)


class MessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Message
        fields = ("id", "role", "content", "sequence", "created_at")


class ConversationSerializer(serializers.ModelSerializer):
    messages = MessageSerializer(many=True, read_only=True)
    result = serializers.SerializerMethodField()

    class Meta:
        model = Conversation
        fields = ("id", "title", "version", "result", "messages", "created_at", "updated_at")

    def get_result(self, obj):
        result = prepare_results_for_display([obj.result], self.context["request"].user)[0]
        api = result.pop("api", None)
        containers = [(result, "preview")] + [(piece, "image") for piece in result.get("pieces", [])]
        for container, key in containers:
            image = container.get(key)
            if isinstance(image, dict) and image.get("kind") == "url":
                match = resolve(image["url"])
                if match.view_name == "wardrobe:item_photo":
                    image["url"] = self.context["request"].build_absolute_uri(
                        reverse("wardrobe_drf:photo", kwargs={"photo_id": match.kwargs["photo_id"]})
                    )
        if api:
            result["match"] = {key: api[key] for key in ("match_mode", "score", "preview_start_status") if key in api}
        return result
