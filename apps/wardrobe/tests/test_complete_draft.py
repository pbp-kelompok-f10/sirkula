from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.db import IntegrityError
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from apps.wardrobe.forms import WardrobeItemDraftCompleteForm
from apps.wardrobe.models import Category, WardrobeItem, WardrobeItemImage, WardrobePhotoCleanup
from .test_private_photos import png_upload


class CompleteDraftTests(TestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        settings = override_settings(WARDROBE_PRIVATE_ROOT=self.root)
        settings.enable()
        self.addCleanup(settings.disable)
        self.owner = get_user_model().objects.create_user(username="complete-owner")
        self.other = get_user_model().objects.create_user(username="complete-other")
        self.category = Category.objects.create(owner=self.owner, name="Atasan")
        self.foreign_category = Category.objects.create(owner=self.other, name="Lain")
        self.draft = WardrobeItem.objects.create(
            owner=self.owner, status=WardrobeItem.Status.DRAFT, name="Belum selesai",
        )
        self.photos = [
            WardrobeItemImage.objects.create(item=self.draft, position=i, image=png_upload(f"{i}.png"))
            for i in (1, 2)
        ]
        self.version = self.draft.updated_at.isoformat()
        self.before = {p.image.name: (self.root / p.image.name).read_bytes() for p in self.photos}
        self.storage = WardrobeItemImage._meta.get_field("image").storage
        self.url = reverse("wardrobe:complete_draft")
        self.client.force_login(self.owner)

    def submit(self, **changes):
        data = {
            "draft_id": self.draft.pk, "version": self.version,
            "name": "Kaos Aktif", "category": self.category.pk,
        }
        data.update(changes)
        return self.client.post(self.url, data)

    def assert_original(self):
        self.draft.refresh_from_db()
        self.assertEqual(self.draft.status, WardrobeItem.Status.DRAFT)
        self.assertEqual(self.draft.name, "Belum selesai")
        self.assertIsNone(self.draft.category_id)
        self.assertEqual(self.draft.updated_at.isoformat(), self.version)
        self.assertEqual(list(self.draft.images.values_list("pk", flat=True)), [p.pk for p in self.photos])
        for name, content in self.before.items():
            self.assertEqual((self.root / name).read_bytes(), content)

    def test_complete_preserves_item_photo_ids_and_files_without_reupload(self):
        with self.captureOnCommitCallbacks(execute=True):
            response = self.submit()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"ok": True, "item": {"id": self.draft.pk}})
        self.draft.refresh_from_db()
        self.assertEqual(self.draft.status, WardrobeItem.Status.ACTIVE)
        self.assertEqual(self.draft.name, "Kaos Aktif")
        self.assertEqual(self.draft.category_id, self.category.pk)
        self.assertEqual(WardrobeItem.objects.count(), 1)
        self.assertEqual(list(self.draft.images.values_list("pk", flat=True)), [p.pk for p in self.photos])
        self.assertEqual({p.image.name: (self.root / p.image.name).read_bytes() for p in self.draft.images.all()}, self.before)
        self.assertEqual(self.client.get(reverse("wardrobe:current_draft")).json()["draft"], None)
        self.assertContains(self.client.get(reverse("wardrobe:index")), "Kaos Aktif")
        self.assertEqual(self.client.get(reverse("wardrobe:item_detail", kwargs={"item_id": self.draft.pk})).status_code, 200)
        self.assertIn("no-store", response["Cache-Control"])

    def test_second_completion_is_conflict_and_does_not_duplicate(self):
        self.assertEqual(self.submit().status_code, 200)
        self.assertEqual(self.submit().status_code, 409)
        self.assertEqual(WardrobeItem.objects.count(), 1)
        self.assertEqual(WardrobeItemImage.objects.count(), 2)

    def test_required_fields_foreign_category_and_wrong_version_are_rejected(self):
        for data, status in (
            ({"name": ""}, 400), ({"category": ""}, 400),
            ({"category": self.foreign_category.pk}, 400),
            ({"version": "stale"}, 409), ({"draft_id": 9999}, 409),
        ):
            with self.subTest(data=data):
                self.assertEqual(self.submit(**data).status_code, status)
                self.assert_original()

    def test_zero_or_more_than_five_final_photos_are_rejected(self):
        data = {"delete_photos": [p.pk for p in self.photos]}
        self.assertEqual(self.submit(**data).status_code, 400)
        self.assert_original()
        self.assertEqual(self.submit(photos=[png_upload(f"new-{i}.png") for i in range(4)]).status_code, 400)
        self.assert_original()

    def test_owner_is_required_and_other_users_cannot_complete_it(self):
        self.assertEqual(self.client.get(self.url).status_code, 405)
        secured = Client(enforce_csrf_checks=True)
        secured.force_login(self.owner)
        self.assertEqual(secured.post(self.url).status_code, 403)
        self.client.force_login(self.other)
        self.assertEqual(self.submit().status_code, 409)
        self.client.logout()
        self.assertEqual(self.submit().status_code, 404)
        self.assert_original()

    def test_complete_with_replacement_photo_cleans_old_after_commit(self):
        with self.captureOnCommitCallbacks(execute=True):
            response = self.submit(delete_photos=[self.photos[0].pk], photos=[png_upload()])
            self.assertTrue(self.storage.exists(self.photos[0].image.name))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(self.storage.exists(self.photos[0].image.name))
        photos = list(self.draft.images.all())
        self.assertEqual([p.position for p in photos], [1, 2])
        self.assertEqual(photos[0].pk, self.photos[1].pk)
        self.assertEqual((self.root / photos[0].image.name).read_bytes(), self.before[photos[0].image.name])
        self.assertFalse(WardrobePhotoCleanup.objects.exists())

    def test_final_database_failure_restores_draft_and_cleans_new_uploads(self):
        with patch.object(WardrobeItem, "save", side_effect=IntegrityError("activation failed")):
            with self.assertLogs("apps.wardrobe.views", level="ERROR"):
                with self.captureOnCommitCallbacks(execute=True) as callbacks:
                    response = self.submit(delete_photos=[self.photos[0].pk], photos=[png_upload()])
        self.assertEqual(response.status_code, 500)
        self.assertEqual(callbacks, [])
        self.assert_original()
        self.assertFalse(WardrobePhotoCleanup.objects.exists())
        self.assertEqual({str(p.relative_to(self.root)) for p in self.root.rglob("*") if p.is_file()}, set(self.before))

    def test_failed_rollback_cleanup_keeps_new_file_reference_for_retry(self):
        with patch.object(WardrobeItem, "save", side_effect=IntegrityError("activation failed")):
            with patch.object(self.storage, "delete", side_effect=OSError("cleanup unavailable")):
                with self.assertLogs("apps.wardrobe", level="ERROR"):
                    response = self.submit(delete_photos=[self.photos[0].pk], photos=[png_upload()])
        self.assertEqual(response.status_code, 500)
        self.assert_original()
        pending = set(WardrobePhotoCleanup.objects.values_list("file_name", flat=True))
        self.assertEqual(len(pending), 1)
        self.assertTrue(pending.isdisjoint(self.before))
        call_command("cleanup_wardrobe_photos", stdout=StringIO())
        self.assertFalse(WardrobePhotoCleanup.objects.exists())
        self.assert_original()

    def test_successful_activation_keeps_failed_old_cleanup_retryable(self):
        with patch.object(self.storage, "delete", side_effect=OSError("cleanup unavailable")):
            with self.assertLogs("apps.wardrobe.cleanup", level="ERROR"):
                with self.captureOnCommitCallbacks(execute=True):
                    response = self.submit(delete_photos=[self.photos[0].pk])
        self.assertEqual(response.status_code, 200)
        self.draft.refresh_from_db()
        self.assertEqual(self.draft.status, WardrobeItem.Status.ACTIVE)
        self.assertTrue(WardrobePhotoCleanup.objects.filter(file_name=self.photos[0].image.name).exists())
        call_command("cleanup_wardrobe_photos", stdout=StringIO())
        self.assertFalse(self.storage.exists(self.photos[0].image.name))
        self.assertTrue(self.storage.exists(self.photos[1].image.name))
        self.assertFalse(WardrobePhotoCleanup.objects.exists())

    def test_completion_form_rejects_missing_instance(self):
        with self.assertRaises(ValueError):
            WardrobeItemDraftCompleteForm(owner=self.owner, instance=None)
