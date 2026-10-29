from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from apps.wardrobe.cleanup import cleanup_pending_photos
from apps.wardrobe.models import (
    Category, WardrobeItem, WardrobeItemImage, WardrobePhotoCleanup,
)
from .test_private_photos import png_upload


class ItemDeleteTests(TestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        settings = override_settings(WARDROBE_PRIVATE_ROOT=self.root)
        settings.enable()
        self.addCleanup(settings.disable)
        self.owner = get_user_model().objects.create_user(username="delete-owner")
        self.other = get_user_model().objects.create_user(username="delete-other")
        self.category = Category.objects.create(owner=self.owner, name="Kaos")
        self.item = WardrobeItem.objects.create(
            owner=self.owner, category=self.category, name="Kaos Hijau"
        )
        self.item_id = self.item.pk
        self.photos = [
            WardrobeItemImage.objects.create(
                item=self.item, image=png_upload(f"{position}.png"), position=position,
            )
            for position in (1, 2)
        ]
        self.names = [photo.image.name for photo in self.photos]
        self.storage = WardrobeItemImage._meta.get_field("image").storage
        self.url = reverse("wardrobe:delete_item", kwargs={"item_id": self.item_id})
        self.client.force_login(self.owner)

    def assert_original(self):
        self.assertTrue(WardrobeItem.objects.filter(pk=self.item_id).exists())
        self.assertEqual(WardrobeItemImage.objects.filter(item_id=self.item_id).count(), 2)
        self.assertTrue(all(self.storage.exists(name) for name in self.names))
        self.assertFalse(WardrobePhotoCleanup.objects.exists())

    def test_owner_deletes_rows_and_files_only_after_commit(self):
        with self.captureOnCommitCallbacks(execute=True) as callbacks:
            response = self.client.post(self.url)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json(), {"ok": True, "item": {"id": self.item_id}})
            self.assertFalse(WardrobeItem.objects.filter(pk=self.item_id).exists())
            self.assertFalse(WardrobeItemImage.objects.filter(item_id=self.item_id).exists())
            self.assertEqual(WardrobePhotoCleanup.objects.count(), 2)
            self.assertTrue(all(self.storage.exists(name) for name in self.names))
        self.assertEqual(len(callbacks), 1)
        self.assertFalse(any(self.storage.exists(name) for name in self.names))
        self.assertFalse(WardrobePhotoCleanup.objects.exists())
        self.assertTrue(Category.objects.filter(pk=self.category.pk).exists())
        self.assertIn("no-store", response["Cache-Control"])
        self.assertIn("Cookie", response["Vary"])

    def test_other_user_anonymous_and_missing_item_are_rejected(self):
        for user in (self.other, None):
            if user is None:
                self.client.logout()
            else:
                self.client.force_login(user)
            self.assertEqual(self.client.post(self.url).status_code, 404)
            self.assert_original()
        self.client.force_login(self.owner)
        url = reverse("wardrobe:delete_item", kwargs={"item_id": self.item_id + 999})
        self.assertEqual(self.client.post(url).status_code, 404)
        self.assert_original()

    def test_get_is_rejected_and_csrf_is_required(self):
        self.assertEqual(self.client.get(self.url).status_code, 405)
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.owner)
        self.assertEqual(client.post(self.url).status_code, 403)
        self.assert_original()

    def test_database_failure_rolls_back_deleted_rows_and_queue(self):
        original_delete = WardrobeItem.delete

        def fail_after_delete(item, *args, **kwargs):
            original_delete(item, *args, **kwargs)
            raise IntegrityError("simulated database failure")

        with patch.object(WardrobeItem, "delete", fail_after_delete):
            with self.assertLogs("apps.wardrobe.views", level="ERROR"):
                with self.captureOnCommitCallbacks(execute=True) as callbacks:
                    response = self.client.post(self.url)
        self.assertEqual(response.status_code, 500)
        self.assertEqual(callbacks, [])
        self.assert_original()

    def test_queue_failure_does_not_delete_item_or_files(self):
        with patch.object(WardrobePhotoCleanup.objects, "get_or_create", side_effect=IntegrityError("queue failed")):
            with self.assertLogs("apps.wardrobe.views", level="ERROR"):
                response = self.client.post(self.url)
        self.assertEqual(response.status_code, 500)
        self.assert_original()

    def test_failed_storage_cleanup_keeps_queue_for_retry(self):
        with patch.object(self.storage, "delete", side_effect=OSError("storage unavailable")):
            with self.assertLogs("apps.wardrobe.cleanup", level="ERROR"):
                with self.captureOnCommitCallbacks(execute=True):
                    response = self.client.post(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(WardrobeItem.objects.filter(pk=self.item_id).exists())
        self.assertEqual(set(WardrobePhotoCleanup.objects.values_list("file_name", flat=True)), set(self.names))
        self.assertTrue(all(self.storage.exists(name) for name in self.names))
        ids = list(WardrobePhotoCleanup.objects.values_list("pk", flat=True))
        cleanup_pending_photos(ids)
        cleanup_pending_photos(ids)
        self.assertFalse(WardrobePhotoCleanup.objects.exists())
        self.assertFalse(any(self.storage.exists(name) for name in self.names))

    def test_unrun_callback_leaves_persistent_cleanup_references(self):
        with self.captureOnCommitCallbacks(execute=False):
            self.assertEqual(self.client.post(self.url).status_code, 200)
        self.assertEqual(WardrobePhotoCleanup.objects.count(), 2)
        self.assertTrue(all(self.storage.exists(name) for name in self.names))
        self.storage.delete(self.names[0])
        cleanup_pending_photos(list(WardrobePhotoCleanup.objects.values_list("pk", flat=True)))
        self.assertFalse(WardrobePhotoCleanup.objects.exists())
        self.assertFalse(any(self.storage.exists(name) for name in self.names))
