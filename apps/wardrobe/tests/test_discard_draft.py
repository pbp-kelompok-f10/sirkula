from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.db import IntegrityError
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from apps.wardrobe.models import Category, WardrobeItem, WardrobeItemImage, WardrobePhotoCleanup
from .test_private_photos import png_upload


class DiscardDraftTests(TestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        settings = override_settings(WARDROBE_PRIVATE_ROOT=self.root)
        settings.enable()
        self.addCleanup(settings.disable)
        self.owner = get_user_model().objects.create_user(username="discard-owner")
        self.other = get_user_model().objects.create_user(username="discard-other")
        self.category = Category.objects.create(owner=self.owner, name="Atasan")
        self.draft = WardrobeItem.objects.create(
            owner=self.owner, category=self.category,
            status=WardrobeItem.Status.DRAFT, name="Draft Awal",
        )
        self.draft_id = self.draft.pk
        self.version = self.draft.updated_at.isoformat()
        self.photos = [
            WardrobeItemImage.objects.create(item=self.draft, position=i, image=png_upload(f"{i}.png"))
            for i in (1, 2)
        ]
        self.before = {p.image.name: (self.root / p.image.name).read_bytes() for p in self.photos}
        self.storage = WardrobeItemImage._meta.get_field("image").storage
        self.url = reverse("wardrobe:discard_draft")
        self.client.force_login(self.owner)

    def submit(self, **changes):
        data = {"draft_id": self.draft_id, "version": self.version}
        data.update(changes)
        return self.client.post(self.url, data)

    def assert_original(self):
        self.draft.refresh_from_db()
        self.assertEqual(self.draft.status, WardrobeItem.Status.DRAFT)
        self.assertEqual(self.draft.name, "Draft Awal")
        self.assertEqual(list(self.draft.images.values_list("pk", flat=True)), [p.pk for p in self.photos])
        self.assertFalse(WardrobePhotoCleanup.objects.exists())
        for name, content in self.before.items():
            self.assertEqual((self.root / name).read_bytes(), content)

    def test_owner_discards_and_files_are_removed_only_after_commit(self):
        active = WardrobeItem.objects.create(owner=self.owner, name="Aktif", category=self.category)
        with self.captureOnCommitCallbacks(execute=True) as callbacks:
            response = self.submit()
            self.assertEqual(response.status_code, 200)
            self.assertFalse(WardrobeItem.objects.filter(pk=self.draft_id).exists())
            self.assertFalse(WardrobeItemImage.objects.filter(item_id=self.draft_id).exists())
            self.assertEqual(WardrobePhotoCleanup.objects.count(), 2)
            self.assertTrue(all(self.storage.exists(name) for name in self.before))
        self.assertEqual(len(callbacks), 1)
        self.assertEqual(response.json(), {"ok": True, "draft": None})
        self.assertFalse(any(self.storage.exists(name) for name in self.before))
        self.assertFalse(WardrobePhotoCleanup.objects.exists())
        self.assertTrue(WardrobeItem.objects.filter(pk=active.pk).exists())
        self.assertTrue(Category.objects.filter(pk=self.category.pk).exists())
        self.assertIn("no-store", response["Cache-Control"])
        self.assertIn("Cookie", response["Vary"])

    def test_anonymous_get_and_missing_csrf_are_rejected(self):
        self.assertEqual(self.client.get(self.url).status_code, 405)
        secured = Client(enforce_csrf_checks=True)
        secured.force_login(self.owner)
        self.assertEqual(secured.post(self.url).status_code, 403)
        self.client.logout()
        self.assertEqual(self.submit().status_code, 404)
        self.assert_original()

    def test_other_user_cannot_discard_owner_draft_or_their_own_using_foreign_id(self):
        other_draft = WardrobeItem.objects.create(owner=self.other, status=WardrobeItem.Status.DRAFT)
        self.client.force_login(self.other)
        self.assertEqual(self.submit().status_code, 409)
        self.assertTrue(WardrobeItem.objects.filter(pk=other_draft.pk).exists())
        self.assert_original()

    def test_stale_missing_version_and_wrong_id_are_conflicts(self):
        for data in ({"version": "stale"}, {"version": ""}, {"draft_id": ""}, {"draft_id": 99999}):
            with self.subTest(data=data):
                response = self.submit(**data)
                self.assertEqual(response.status_code, 409)
                self.assertEqual(response.json()["errors"]["__all__"][0]["code"], "draft_conflict")
                self.assert_original()

    def test_old_request_cannot_discard_replacement_draft(self):
        self.draft.delete()
        replacement = WardrobeItem.objects.create(owner=self.owner, status=WardrobeItem.Status.DRAFT)
        self.assertEqual(self.submit().status_code, 409)
        self.assertTrue(WardrobeItem.objects.filter(pk=replacement.pk).exists())
        self.assertTrue(all(self.storage.exists(name) for name in self.before))

    def test_active_item_is_not_discarded(self):
        WardrobeItem.objects.filter(pk=self.draft_id).update(status=WardrobeItem.Status.ACTIVE)
        self.assertEqual(self.submit().status_code, 409)
        self.draft.refresh_from_db()
        self.assertEqual(self.draft.status, WardrobeItem.Status.ACTIVE)
        self.assertEqual(self.draft.images.count(), 2)
        self.assertTrue(all(self.storage.exists(name) for name in self.before))

    def test_database_failure_restores_rows_and_queue_and_keeps_files(self):
        original_delete = WardrobeItem.delete

        def fail_after_delete(item, *args, **kwargs):
            original_delete(item, *args, **kwargs)
            raise IntegrityError("delete failed")

        with patch.object(WardrobeItem, "delete", new=fail_after_delete):
            with self.assertLogs("apps.wardrobe.views", level="ERROR"):
                with self.captureOnCommitCallbacks(execute=True) as callbacks:
                    response = self.submit()
        self.assertEqual(response.status_code, 500)
        self.assertEqual(callbacks, [])
        self.assert_original()

    def test_queue_failure_keeps_draft_and_files(self):
        with patch("apps.wardrobe.views.queue_photo_cleanup", side_effect=IntegrityError("queue failed")):
            with self.assertLogs("apps.wardrobe.views", level="ERROR"):
                response = self.submit()
        self.assertEqual(response.status_code, 500)
        self.assert_original()

    def test_failed_storage_cleanup_is_persistent_and_retryable(self):
        with patch.object(self.storage, "delete", side_effect=OSError("storage unavailable")):
            with self.assertLogs("apps.wardrobe.cleanup", level="ERROR"):
                with self.captureOnCommitCallbacks(execute=True):
                    response = self.submit()
        self.assertEqual(response.status_code, 200)
        self.assertFalse(WardrobeItem.objects.filter(pk=self.draft_id).exists())
        self.assertEqual(set(WardrobePhotoCleanup.objects.values_list("file_name", flat=True)), set(self.before))
        call_command("cleanup_wardrobe_photos", stdout=StringIO())
        self.assertFalse(WardrobePhotoCleanup.objects.exists())
        self.assertFalse(any(self.storage.exists(name) for name in self.before))
        self.assertEqual(self.submit().status_code, 409)

    def test_draft_without_photos_can_be_discarded(self):
        self.draft.images.all().delete()
        with self.captureOnCommitCallbacks(execute=True):
            self.assertEqual(self.submit().status_code, 200)
        self.assertFalse(WardrobeItem.objects.filter(pk=self.draft_id).exists())
        self.assertFalse(WardrobePhotoCleanup.objects.exists())
