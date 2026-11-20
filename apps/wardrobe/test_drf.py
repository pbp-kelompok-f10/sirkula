from pathlib import Path
from tempfile import TemporaryDirectory

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import include, path, reverse
from rest_framework.test import APIClient

from .models import Category, WardrobeItem, WardrobeItemImage
from .tests.test_private_photos import png_upload

urlpatterns = [path("api/", include("apps.wardrobe.api_urls_drf"))]


@override_settings(ROOT_URLCONF=__name__)
class WardrobeDRFTests(TestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        settings = override_settings(WARDROBE_PRIVATE_ROOT=Path(directory.name))
        settings.enable()
        self.addCleanup(settings.disable)
        self.owner = get_user_model().objects.create_user(username="drf-owner")
        self.other = get_user_model().objects.create_user(username="drf-other")
        self.category = Category.objects.get(owner=self.owner, name="Kaos")
        self.other_category = Category.objects.get(owner=self.other, name="Kaos")
        self.client = APIClient()
        self.client.force_authenticate(self.owner)
    def test_authentication_required(self):
        self.client.force_authenticate(user=None)
        self.assertIn(self.client.get(reverse("wardrobe_drf:items")).status_code, (401, 403))
        self.assertIn(self.client.get(reverse("wardrobe_drf:categories")).status_code, (401, 403))


    def test_active_requires_owned_category_and_photo(self):
        url = reverse("wardrobe_drf:items")
        response = self.client.post(url, {"name": "Baju", "category": self.other_category.pk, "photos": [png_upload()]}, format="multipart")
        self.assertEqual(response.status_code, 400)
        response = self.client.post(url, {"name": "Baju", "category": self.category.pk}, format="multipart")
        self.assertEqual(response.status_code, 400)
        response = self.client.post(url, {"name": "Baju", "category": self.category.pk, "photos": [png_upload()]}, format="multipart")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(WardrobeItem.objects.get(pk=response.data["id"]).owner, self.owner)

    def test_ownership_and_photo_access(self):
        item = WardrobeItem.objects.create(owner=self.other, name="Private", category=self.other_category)
        photo = WardrobeItemImage.objects.create(item=item, image=png_upload(), position=1)
        self.assertEqual(self.client.get(reverse("wardrobe_drf:item", args=[item.pk])).status_code, 404)
        self.assertEqual(self.client.delete(reverse("wardrobe_drf:item", args=[item.pk])).status_code, 404)
        self.assertEqual(self.client.get(reverse("wardrobe_drf:photo", args=[photo.pk])).status_code, 404)
        self.assertNotIn(item.pk, [entry["id"] for entry in self.client.get(reverse("wardrobe_drf:items")).data])

    def test_draft_completion_and_single_draft(self):
        url = reverse("wardrobe_drf:items")
        first = self.client.post(url, {"name": "Draft", "status": "draft"}, format="json")
        self.assertEqual(first.status_code, 201)
        self.assertEqual(self.client.post(url, {"name": "Lain", "status": "draft"}, format="json").status_code, 400)
        detail = reverse("wardrobe_drf:item", args=[first.data["id"]])
        self.assertEqual(self.client.patch(detail, {"status": "active"}, format="json").status_code, 400)
        response = self.client.patch(detail, {"status": "active", "category": self.category.pk, "photos": [png_upload()]}, format="multipart")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "active")

    def test_deleting_last_photo_is_rejected(self):
        item = WardrobeItem.objects.create(owner=self.owner, name="Baju", category=self.category)
        photo = WardrobeItemImage.objects.create(item=item, image=png_upload(), position=1)
        response = self.client.patch(reverse("wardrobe_drf:item", args=[item.pk]), {"delete_photos": [photo.pk]}, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertTrue(item.images.filter(pk=photo.pk).exists())
