import uuid

from django.conf import settings
from django.db import models


class Conversation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="outfit_conversations")
    title = models.CharField(max_length=100)
    creation_key = models.UUIDField()
    initial_recommendation = models.CharField(max_length=50, blank=True)
    result = models.JSONField(default=dict)
    version = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at", "-id"]
        constraints = [
            models.UniqueConstraint(fields=["owner", "creation_key"], name="outfits_unique_creation_per_owner"),
            models.CheckConstraint(condition=models.Q(version__gte=1), name="outfits_conversation_version_positive"),
        ]


class Message(models.Model):
    class Role(models.TextChoices):
        USER = "user", "Pengguna"
        ASSISTANT = "assistant", "SirkulaAI"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name="messages")
    role = models.CharField(max_length=10, choices=Role.choices)
    content = models.TextField()
    sequence = models.PositiveIntegerField()
    request_key = models.UUIDField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["sequence"]
        constraints = [
            models.UniqueConstraint(fields=["conversation", "sequence"], name="outfits_unique_message_sequence"),
            models.UniqueConstraint(fields=["conversation", "request_key", "role"], name="outfits_unique_message_request_role"),
            models.CheckConstraint(condition=models.Q(sequence__gte=1), name="outfits_message_sequence_positive"),
            models.CheckConstraint(condition=models.Q(role__in=["user", "assistant"]), name="outfits_message_role_valid"),
        ]
