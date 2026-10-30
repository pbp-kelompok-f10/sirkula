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
        STATUS = "status", "Status aplikasi"

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
            models.CheckConstraint(condition=models.Q(role__in=["user", "assistant", "status"]), name="outfits_message_role_valid"),
        ]


class WardrobeAPIAccount(models.Model):
    owner = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="outfits_api_account")
    namespace = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    endpoint = models.URLField()
    lease_token = models.UUIDField(null=True, editable=False)
    lease_until = models.DateTimeField(null=True, editable=False)

    @property
    def api_owner(self):
        return f"sirkula:{self.namespace.hex}"


class WardrobeAPIMapping(models.Model):
    account = models.ForeignKey(WardrobeAPIAccount, on_delete=models.CASCADE, related_name="mappings")
    item = models.OneToOneField("wardrobe.WardrobeItem", null=True, on_delete=models.SET_NULL, related_name="api_mapping")
    api_id = models.CharField(max_length=64, null=True)
    category = models.CharField(max_length=6, choices=[("baju", "Baju"), ("celana", "Celana")])
    checksum = models.CharField(max_length=64)
    photo_id = models.PositiveBigIntegerField()
    item_version = models.CharField(max_length=40)
    revision = models.CharField(max_length=64, blank=True)
    upload_pending = models.BooleanField(default=False)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["account", "api_id"], name="outfits_api_id_per_account")]


class OutfitPreviewBudget(models.Model):
    # A single installation-wide counter; increasing the allowance requires host configuration.
    id = models.PositiveSmallIntegerField(primary_key=True, default=1)
    attempts = models.PositiveIntegerField(default=0)


class OutfitPreviewAttempt(models.Model):
    account = models.ForeignKey(WardrobeAPIAccount, on_delete=models.CASCADE)
    pair_key = models.CharField(max_length=64)
    api_preview_id = models.CharField(max_length=64, blank=True)
    status = models.CharField(max_length=24, default="pending")

    class Meta:
        constraints = [models.UniqueConstraint(fields=["account", "pair_key"], name="outfits_preview_once_per_pair")]
