from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.wardrobe.models import WardrobeItem, WardrobeItemImage
from apps.wardrobe.tests.test_private_photos import png_upload
from .models import Conversation
from .test_api import MemoryAPI


@override_settings(OUTFITS_PROVIDER="api", OUTFITS_PREVIEW_ENABLED=False, OUTFITS_PREVIEW_MAX_REQUESTS=0)
class PartnerLoginWardrobeIntegrationTests(TestCase):
    def test_email_login_wardrobe_matching_and_private_photo_access(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        settings = override_settings(WARDROBE_PRIVATE_ROOT=Path(directory.name))
        settings.enable()
        self.addCleanup(settings.disable)
        owner = get_user_model().objects.create_user("merge-owner", "merge-owner@example.test", "MergeTest-2026!")
        other = get_user_model().objects.create_user("merge-other", "merge-other@example.test", "MergeTest-2026!")
        self.assertEqual(owner.wardrobe_categories.count(), 5)
        self.assertTrue(hasattr(owner, "profile"))
        for name, category in (("Kaos integrasi", "Kaos"), ("Celana integrasi", "Celana")):
            item = WardrobeItem.objects.create(owner=owner, name=name, category=owner.wardrobe_categories.get(name=category))
            WardrobeItemImage.objects.create(item=item, image=png_upload(), position=1)
        response = self.client.post(reverse("accounts:login"), {
            "username": owner.email, "password": "MergeTest-2026!", "next": reverse("wardrobe:index"),
        })
        self.assertRedirects(response, reverse("wardrobe:index"))
        page = self.client.get(reverse("wardrobe:index"))
        self.assertContains(page, "Kaos integrasi")
        self.assertContains(page, reverse("outfits:index"))
        remote = MemoryAPI()
        with patch("apps.outfits.api_provider.WardrobeAPIClient", return_value=remote):
            response = self.client.post(reverse("outfits:index"), {"prompt": "best", "request_key": uuid4()})
        current = Conversation.objects.get(owner=owner)
        self.assertRedirects(response, reverse("outfits:conversation", kwargs={"conversation_id": current.pk}))
        self.assertEqual(current.messages.last().role, "status")
        self.assertEqual(remote.preview_calls, 0)
        image_url = reverse("wardrobe:item_photo", kwargs={"photo_id": current.result["preview"]["photo_id"]})
        photo_response = self.client.get(image_url)
        self.assertEqual(photo_response.status_code, 200)
        photo_response.close()
        self.client.force_login(other)
        self.assertEqual(self.client.get(image_url).status_code, 404)
        self.assertEqual(self.client.get(response.url).status_code, 404)
