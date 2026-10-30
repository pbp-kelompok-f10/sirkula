from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import IntegrityError
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.wardrobe.cleanup import cleanup_pending_photos, queue_photo_cleanup
from apps.wardrobe.models import Category, WardrobeItem, WardrobeItemImage, WardrobePhotoCleanup
from .test_private_photos import png_upload


class PersistentCleanupTests(TestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        settings = override_settings(WARDROBE_PRIVATE_ROOT=self.root)
        settings.enable()
        self.addCleanup(settings.disable)
        owner = get_user_model().objects.create_user(username="cleanup-owner")
        other = get_user_model().objects.create_user(username="cleanup-other")
        self.category = Category.objects.create(owner=owner, name="Atasan")
        self.item = WardrobeItem.objects.create(owner=owner, category=self.category, name="Awal")
        self.photos = [
            WardrobeItemImage.objects.create(item=self.item, position=i, image=png_upload(f"old-{i}.png"))
            for i in (1, 2)
        ]
        other_item = WardrobeItem.objects.create(owner=other, name="Privat Lain")
        self.foreign_photo = WardrobeItemImage.objects.create(item=other_item, position=1, image=png_upload("foreign.png"))
        self.storage = WardrobeItemImage._meta.get_field("image").storage
        self.original_files = self.active_files()
        self.original_rows = list(WardrobeItemImage.objects.order_by("pk").values_list("pk", "image", "position", "item_id"))
        self.edit_url = reverse("wardrobe:update_item", kwargs={"item_id": self.item.pk})
        self.create_url = reverse("wardrobe:create_item")
        self.client.force_login(owner)

    def active_files(self):
        return {
            name: (self.root / name).read_bytes()
            for name in WardrobeItemImage.objects.values_list("image", flat=True)
        }

    def assert_original_rows_and_files(self):
        self.item.refresh_from_db()
        self.assertEqual(self.item.name, "Awal")
        self.assertEqual(list(WardrobeItemImage.objects.order_by("pk").values_list("pk", "image", "position", "item_id")), self.original_rows)
        self.assertEqual(self.active_files(), self.original_files)

    def retry(self):
        call_command("cleanup_wardrobe_photos", stdout=StringIO(), batch_size=1)

    def edit(self):
        return self.client.post(self.edit_url, {
            "name": "Diubah", "category": self.category.pk,
            "delete_photos": [self.photos[0].pk], "photos": [png_upload("new.png")],
        })

    def test_edit_cleanup_failure_is_queued_and_retry_preserves_active_photos(self):
        old_name = self.photos[0].image.name
        original_delete = self.storage.delete

        def fail_old(name):
            if name == old_name:
                raise OSError("temporary storage failure")
            return original_delete(name)

        with self.assertLogs("apps.wardrobe.cleanup", level="ERROR"):
            with patch.object(self.storage, "delete", side_effect=fail_old):
                with self.captureOnCommitCallbacks(execute=True):
                    response = self.edit()
                    self.assertTrue(WardrobePhotoCleanup.objects.filter(file_name=old_name).exists())
                    self.assertTrue(self.storage.exists(old_name))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(WardrobePhotoCleanup.objects.values_list("file_name", flat=True)), [old_name])
        self.assertFalse(WardrobeItemImage.objects.filter(pk=self.photos[0].pk).exists())
        active_before_retry = self.active_files()
        self.retry()
        self.assertFalse(self.storage.exists(old_name))
        self.assertFalse(WardrobePhotoCleanup.objects.exists())
        self.assertEqual(self.active_files(), active_before_retry)
        self.retry()
        self.assertEqual(self.active_files(), active_before_retry)

    def test_edit_queue_survives_callback_not_running(self):
        with self.captureOnCommitCallbacks(execute=False):
            self.assertEqual(self.edit().status_code, 200)
        old_name = self.photos[0].image.name
        self.assertTrue(WardrobePhotoCleanup.objects.filter(file_name=old_name).exists())
        self.assertTrue(self.storage.exists(old_name))
        active_before_retry = self.active_files()
        self.retry()
        self.assertFalse(self.storage.exists(old_name))
        self.assertEqual(self.active_files(), active_before_retry)

    def test_edit_rollback_only_queues_new_upload_when_cleanup_also_fails(self):
        original_save = WardrobeItemImage.save

        def fail_new(photo, *args, **kwargs):
            if photo.pk is None:
                raise IntegrityError("photo insert failed")
            return original_save(photo, *args, **kwargs)

        with self.assertLogs("apps.wardrobe", level="ERROR"):
            with patch.object(WardrobeItemImage, "save", new=fail_new):
                with patch.object(self.storage, "delete", side_effect=OSError("cleanup unavailable")):
                    with self.captureOnCommitCallbacks(execute=True) as callbacks:
                        response = self.edit()
        self.assertEqual(response.status_code, 500)
        self.assertEqual(callbacks, [])
        self.assert_original_rows_and_files()
        names = set(WardrobePhotoCleanup.objects.values_list("file_name", flat=True))
        self.assertEqual(len(names), 1)
        self.assertTrue(names.isdisjoint(self.original_files))
        self.assertTrue(all(self.storage.exists(name) for name in names))
        self.retry()
        self.assertFalse(WardrobePhotoCleanup.objects.exists())
        self.assertTrue(all(not self.storage.exists(name) for name in names))
        self.assert_original_rows_and_files()

    def test_create_database_failure_and_failed_cleanup_are_retryable(self):
        with self.assertLogs("apps.wardrobe", level="ERROR"):
            with patch.object(WardrobeItemImage, "save", side_effect=IntegrityError("photo insert failed")):
                with patch.object(self.storage, "delete", side_effect=OSError("cleanup unavailable")):
                    response = self.client.post(self.create_url, {
                        "name": "Baru", "category": self.category.pk, "photos": [png_upload()],
                    })
        self.assertEqual(response.status_code, 500)
        self.assertFalse(WardrobeItem.objects.filter(name="Baru").exists())
        self.assert_original_rows_and_files()
        names = set(WardrobePhotoCleanup.objects.values_list("file_name", flat=True))
        self.assertEqual(len(names), 1)
        self.assertTrue(names.isdisjoint(self.original_files))
        self.retry()
        self.assertFalse(WardrobePhotoCleanup.objects.exists())
        self.assertTrue(all(not self.storage.exists(name) for name in names))
        self.assert_original_rows_and_files()

    def test_partial_create_upload_failure_and_failed_cleanup_are_retryable(self):
        original_save = self.storage.save
        calls = 0

        def fail_second(*args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError("second upload failed")
            return original_save(*args, **kwargs)

        with self.assertLogs("apps.wardrobe", level="ERROR"):
            with patch.object(self.storage, "save", side_effect=fail_second):
                with patch.object(self.storage, "delete", side_effect=OSError("cleanup unavailable")):
                    response = self.client.post(self.create_url, {
                        "name": "Baru", "category": self.category.pk,
                        "photos": [png_upload("a.png"), png_upload("b.png")],
                    })
        self.assertEqual(response.status_code, 500)
        self.assertFalse(WardrobeItem.objects.filter(name="Baru").exists())
        self.assertEqual(WardrobePhotoCleanup.objects.count(), 1)
        self.retry()
        self.assertFalse(WardrobePhotoCleanup.objects.exists())
        self.assert_original_rows_and_files()
        self.assertEqual(len([p for p in self.root.rglob("*") if p.is_file()]), len(self.original_files))

    def test_retry_never_deletes_referenced_files_for_any_owner(self):
        protected = [self.photos[0].image.name, self.foreign_photo.image.name]
        queue_photo_cleanup(protected)
        orphan_name = self.storage.save("photos/orphan.png", png_upload())
        queue_photo_cleanup([orphan_name])
        with patch.object(self.storage, "delete", wraps=self.storage.delete) as delete:
            with self.assertLogs("apps.wardrobe.cleanup", level="WARNING"):
                with self.assertRaises(CommandError):
                    self.retry()
        self.assertEqual([call.args[0] for call in delete.call_args_list], [orphan_name])
        self.assertFalse(self.storage.exists(orphan_name))
        self.assertEqual(set(WardrobePhotoCleanup.objects.values_list("file_name", flat=True)), set(protected))
        self.assert_original_rows_and_files()

    def test_previously_protected_file_can_be_cleaned_when_no_longer_referenced(self):
        photo = self.photos[0]
        ids = queue_photo_cleanup([photo.image.name])
        with self.assertLogs("apps.wardrobe.cleanup", level="WARNING"):
            cleanup_pending_photos(ids)
        self.assertTrue(self.storage.exists(photo.image.name))
        photo.delete()
        self.retry()
        self.assertFalse(self.storage.exists(photo.image.name))
        self.assertFalse(WardrobePhotoCleanup.objects.exists())
        self.assertTrue(self.storage.exists(self.photos[1].image.name))
        self.assertTrue(self.storage.exists(self.foreign_photo.image.name))

    def test_queue_deduplicates_names_and_ignores_empty_names(self):
        self.assertEqual(queue_photo_cleanup([]), ())
        first = queue_photo_cleanup(["photos/orphan.png", "", "photos/orphan.png"])
        self.assertEqual(len(first), 1)
        self.assertEqual(queue_photo_cleanup(["photos/orphan.png"]), first)
        self.assertEqual(WardrobePhotoCleanup.objects.count(), 1)

    def test_queue_remains_when_deleting_queue_row_fails_after_file_removed(self):
        name = self.storage.save("photos/orphan.png", png_upload())
        ids = queue_photo_cleanup([name])
        with self.assertLogs("apps.wardrobe.cleanup", level="ERROR"):
            with patch.object(WardrobePhotoCleanup, "delete", side_effect=IntegrityError("queue delete failed")):
                cleanup_pending_photos(ids)
        self.assertFalse(self.storage.exists(name))
        self.assertTrue(WardrobePhotoCleanup.objects.filter(pk=ids[0]).exists())
        self.retry()
        self.assertFalse(WardrobePhotoCleanup.objects.exists())
        self.assert_original_rows_and_files()

    def test_queue_insert_failure_rolls_back_edit_before_old_files_removed(self):
        original_get_or_create = WardrobePhotoCleanup.objects.get_or_create
        old_name = self.photos[0].image.name

        def fail_old_queue(*args, **kwargs):
            if kwargs.get("file_name") == old_name:
                raise IntegrityError("old photo queue insert failed")
            return original_get_or_create(*args, **kwargs)

        with self.assertLogs("apps.wardrobe.views", level="ERROR"):
            with patch.object(WardrobePhotoCleanup.objects, "get_or_create", side_effect=fail_old_queue):
                with self.captureOnCommitCallbacks(execute=True) as callbacks:
                    response = self.edit()
        self.assertEqual(response.status_code, 500)
        self.assertEqual(callbacks, [])
        self.assert_original_rows_and_files()
        self.assertFalse(WardrobePhotoCleanup.objects.exists())
        self.assertEqual(len([p for p in self.root.rglob("*") if p.is_file()]), len(self.original_files))

    def test_queue_batch_insert_failure_rolls_back_partial_queue(self):
        original_get_or_create = WardrobePhotoCleanup.objects.get_or_create

        def fail_second(*args, **kwargs):
            if kwargs.get("file_name") == "photos/fail.png":
                raise IntegrityError("queue insert failed")
            return original_get_or_create(*args, **kwargs)

        with patch.object(WardrobePhotoCleanup.objects, "get_or_create", side_effect=fail_second):
            with self.assertRaises(IntegrityError):
                queue_photo_cleanup(["photos/first.png", "photos/fail.png"])
        self.assertFalse(WardrobePhotoCleanup.objects.exists())
        self.assert_original_rows_and_files()
