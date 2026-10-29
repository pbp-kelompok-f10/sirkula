from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.wardrobe.models import Category, WardrobeItem, WardrobeItemImage, WardrobePhotoCleanup
from .test_private_photos import png_upload


class DraftModalIntegrationTests(TestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        settings = override_settings(WARDROBE_PRIVATE_ROOT=self.root)
        settings.enable()
        self.addCleanup(settings.disable)
        self.owner = get_user_model().objects.create_user(username="draft-modal-owner")
        self.other = get_user_model().objects.create_user(username="draft-modal-other")
        self.category = Category.objects.create(owner=self.owner, name="Atasan")
        self.client.force_login(self.owner)

    def test_modal_exposes_draft_actions_and_confirmation_to_owner(self):
        response = self.client.get(reverse("wardrobe:index"), {"category": self.category.pk})
        for endpoint in ("current_draft", "save_draft", "complete_draft", "discard_draft"):
            self.assertContains(response, reverse(f"wardrobe:{endpoint}"))
        for element in ("save-item-draft", "item-saved-photos", "draft-discard-modal", "cancel-draft-discard"):
            self.assertContains(response, f'id="{element}"')
        self.assertContains(response, 'id="discard-item-draft"')
        self.assertEqual(response.context["active_category_id"], self.category.pk)
        self.client.logout()
        response = self.client.get(reverse("wardrobe:index"))
        self.assertNotContains(response, 'id="item-form"')
        self.assertNotContains(response, 'id="draft-discard-modal"')

    def test_json_add_without_draft_preserves_existing_create_flow(self):
        response = self.client.post(reverse("wardrobe:create_item"), {
            "name": "Pakaian biasa", "category": self.category.pk, "photos": [png_upload()],
        }, HTTP_ACCEPT="application/json")
        self.assertEqual(response.status_code, 200)
        item = WardrobeItem.objects.get(pk=response.json()["item"]["id"])
        self.assertEqual(item.owner, self.owner)
        self.assertEqual(item.status, WardrobeItem.Status.ACTIVE)
        self.assertEqual(item.images.count(), 1)
        self.assertFalse(WardrobeItem.objects.filter(status=WardrobeItem.Status.DRAFT).exists())

    def test_json_add_validation_reports_fields_without_creating_item(self):
        response = self.client.post(reverse("wardrobe:create_item"), {}, HTTP_ACCEPT="application/json")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(set(response.json()["errors"]), {"name", "category", "photos"})
        self.assertFalse(WardrobeItem.objects.exists())

    def test_json_add_storage_failure_rolls_back_and_queues_cleanup(self):
        storage = WardrobeItemImage._meta.get_field("image").storage
        with patch.object(WardrobeItemImage, "save", side_effect=OSError("database unavailable")):
            with patch.object(storage, "delete", side_effect=OSError("storage unavailable")):
                with self.assertLogs("apps.wardrobe", level="ERROR"):
                    response = self.client.post(reverse("wardrobe:create_item"), {
                        "name": "Baru", "category": self.category.pk, "photos": [png_upload()],
                    }, HTTP_ACCEPT="application/json")
        self.assertEqual(response.status_code, 500)
        self.assertIn("__all__", response.json()["errors"])
        self.assertFalse(WardrobeItem.objects.exists())
        self.assertEqual(WardrobePhotoCleanup.objects.count(), 1)

    def test_partial_save_reopen_complete_reuses_item_and_private_photo(self):
        self.assertIsNone(self.client.get(reverse("wardrobe:current_draft")).json()["draft"])
        saved = self.client.post(reverse("wardrobe:save_draft"), {"photos": [png_upload()]}).json()["draft"]
        photo = WardrobeItemImage.objects.get(pk=saved["photos"][0]["id"])
        content = (self.root / photo.image.name).read_bytes()
        for _ in range(2):
            loaded = self.client.get(reverse("wardrobe:current_draft")).json()["draft"]
            self.assertEqual(loaded, saved)
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(saved["photos"][0]["url"]).status_code, 404)
        self.client.force_login(self.owner)
        response = self.client.post(reverse("wardrobe:complete_draft"), {
            "draft_id": saved["id"], "version": saved["version"],
            "name": "Dari Draft", "category": self.category.pk,
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["item"]["id"], saved["id"])
        self.assertEqual(WardrobeItemImage.objects.get().pk, photo.pk)
        self.assertEqual((self.root / photo.image.name).read_bytes(), content)
        self.assertIsNone(self.client.get(reverse("wardrobe:current_draft")).json()["draft"])
        response = self.client.get(reverse("wardrobe:index"), {"category": self.category.pk})
        self.assertEqual([item.pk for item in response.context["clothes"]], [saved["id"]])

    def test_discard_saved_draft_preserves_active_clothing_and_allows_fresh_add(self):
        active = WardrobeItem.objects.create(owner=self.owner, name="Tetap aman", category=self.category)
        active_photo = WardrobeItemImage.objects.create(item=active, image=png_upload(), position=1)
        saved = self.client.post(reverse("wardrobe:save_draft"), {"name": "Draft", "photos": [png_upload()]}).json()["draft"]
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(reverse("wardrobe:discard_draft"), {"draft_id": saved["id"], "version": saved["version"]})
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(self.client.get(reverse("wardrobe:current_draft")).json()["draft"])
        self.assertTrue((self.root / active_photo.image.name).exists())
        response = self.client.post(reverse("wardrobe:create_item"), {"name": "Mulai baru", "category": self.category.pk, "photos": [png_upload()]}, HTTP_ACCEPT="application/json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(WardrobeItem.objects.filter(status=WardrobeItem.Status.ACTIVE).count(), 2)

    def test_default_html_add_still_redirects(self):
        response = self.client.post(reverse("wardrobe:create_item"), {"name": "HTML", "category": self.category.pk, "photos": [png_upload()]})
        self.assertRedirects(response, reverse("wardrobe:index"))
