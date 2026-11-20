from unittest.mock import patch
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import include, path, reverse
from rest_framework.test import APIClient

from .api_client import WardrobeAPIError
from .models import Conversation, Message
from .services import ConversationConflict

urlpatterns = [
    path("api/outfits/", include("apps.outfits.api_urls_drf")),
    path("api/wardrobe/", include("apps.wardrobe.api_urls_drf")),
    path("wardrobe/", include("apps.wardrobe.urls")),
]


@override_settings(ROOT_URLCONF=__name__)
class OutfitDRFTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user(username="stylist-owner")
        self.other = get_user_model().objects.create_user(username="stylist-other")
        self.conversation = Conversation.objects.create(owner=self.owner, title="Outfit", creation_key=uuid4(), result={})
        self.client = APIClient()
        self.client.force_authenticate(self.owner)

    def test_conversations_are_private(self):
        foreign = Conversation.objects.create(owner=self.other, title="Private", creation_key=uuid4(), result={})
        self.assertEqual(self.client.get(reverse("outfits_drf:conversation", args=[foreign.pk])).status_code, 404)
        self.assertEqual(self.client.post(reverse("outfits_drf:messages", args=[foreign.pk]), {}, format="json").status_code, 404)
        self.assertEqual([row["id"] for row in self.client.get(reverse("outfits_drf:conversations")).data], [str(self.conversation.pk)])

    def test_start_uses_service_and_reports_failures(self):
        url = reverse("outfits_drf:conversations")
        key = uuid4()
        with patch("apps.outfits.api_views_drf.start_conversation", return_value=self.conversation) as service:
            response = self.client.post(url, {"prompt": "  best  ", "request_key": str(key)}, format="json")
        self.assertEqual(response.status_code, 201)
        service.assert_called_once_with(user=self.owner, prompt="best", key=key, recommendation="")
        with patch("apps.outfits.api_views_drf.start_conversation", side_effect=WardrobeAPIError(code="configuration")):
            response = self.client.post(url, {"prompt": "best", "request_key": str(key)}, format="json")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.data["code"], "configuration")

    def test_message_conflict_and_input_validation(self):
        url = reverse("outfits_drf:messages", args=[self.conversation.pk])
        self.assertEqual(self.client.post(url, {"prompt": "test", "request_key": str(uuid4()), "version": 0}, format="json").status_code, 400)
        with patch("apps.outfits.api_views_drf.send_message", side_effect=ConversationConflict("stale")):
            response = self.client.post(url, {"prompt": "test", "request_key": str(uuid4()), "version": 1}, format="json")
        self.assertEqual(response.status_code, 409)
        self.assertFalse(Message.objects.filter(conversation=self.conversation).exists())

    def test_preview_get_does_not_enqueue(self):
        with patch("apps.outfits.api_views_drf.enqueue_preview") as enqueue, patch("apps.outfits.api_views_drf.read_preview_status", return_value={"preview_status": "not_generated"}):
            response = self.client.get(reverse("outfits_drf:preview", args=[self.conversation.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.data["preview_url"])
        enqueue.assert_not_called()
