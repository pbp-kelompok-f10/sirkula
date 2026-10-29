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


class SaveDraftTests(TestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        settings = override_settings(WARDROBE_PRIVATE_ROOT=self.root)
        settings.enable()
        self.addCleanup(settings.disable)
        self.owner = get_user_model().objects.create_user(username="save-draft-owner")
        self.other = get_user_model().objects.create_user(username="save-draft-other")
        self.category = Category.objects.create(owner=self.owner, name="Atasan")
        self.foreign_category = Category.objects.create(owner=self.other, name="Lain")
        self.storage = WardrobeItemImage._meta.get_field("image").storage
        self.url = reverse("wardrobe:save_draft")
        self.client.force_login(self.owner)

    def create_saved_draft(self, photos=2):
        self.draft = WardrobeItem.objects.create(
            owner=self.owner, status=WardrobeItem.Status.DRAFT,
            name="Draft Awal", category=self.category,
        )
        self.photos = [
            WardrobeItemImage.objects.create(
                item=self.draft, position=i, image=png_upload(f"old-{i}.png"),
            ) for i in range(1, photos + 1)
        ]
        self.before = {p.image.name: (self.root / p.image.name).read_bytes() for p in self.photos}
        self.version = self.draft.updated_at.isoformat()
        return self.draft

    def submit(self, **data):
        payload = {
            "draft_id": self.draft.pk,
            "version": self.version,
            "name": "Draft Diubah",
            "category": self.category.pk,
        }
        payload.update(data)
        return self.client.post(self.url, payload)

    def assert_original(self):
        self.draft.refresh_from_db()
        self.assertEqual(self.draft.name, "Draft Awal")
        self.assertEqual(self.draft.updated_at.isoformat(), self.version)
        self.assertEqual(list(self.draft.images.values_list("pk", flat=True)), [p.pk for p in self.photos])
        for name, content in self.before.items():
            self.assertEqual((self.root / name).read_bytes(), content)

    def test_create_partial_and_update_same_draft_with_returned_version(self):
        first = self.client.post(self.url, {"name": "Nama saja"})
        self.assertEqual(first.status_code, 200)
        initial = first.json()["draft"]
        second = self.client.post(self.url, {
            "draft_id": initial["id"], "version": initial["version"],
            "category": self.category.pk,
        })
        self.assertEqual(second.status_code, 200)
        result = second.json()["draft"]
        self.assertEqual(result["id"], initial["id"])
        self.assertNotEqual(result["version"], initial["version"])
        self.assertEqual(result["name"], "")
        self.assertEqual(result["category"]["id"], self.category.pk)
        self.assertEqual(WardrobeItem.objects.filter(owner=self.owner).count(), 1)
        self.assertEqual(WardrobeItem.objects.get(pk=result["id"]).status, WardrobeItem.Status.DRAFT)

    def test_photo_only_draft_can_be_loaded_and_stays_out_of_collection(self):
        response = self.client.post(self.url, {"photos": [png_upload()]})
        self.assertEqual(response.status_code, 200)
        result = response.json()["draft"]
        self.assertEqual(result["name"], "")
        self.assertIsNone(result["category"])
        self.assertEqual(len(result["photos"]), 1)
        self.assertEqual(self.client.get(reverse("wardrobe:current_draft")).json()["draft"], result)
        self.assertEqual(list(self.client.get(reverse("wardrobe:index")).context["clothes"]), [])

    def test_anonymous_get_and_missing_csrf_are_rejected(self):
        self.assertEqual(self.client.get(self.url).status_code, 405)
        secured = Client(enforce_csrf_checks=True)
        secured.force_login(self.owner)
        self.assertEqual(secured.post(self.url, {"name": "Draft"}).status_code, 403)
        self.client.logout()
        self.assertEqual(self.client.post(self.url, {"name": "Draft"}).status_code, 404)
        self.assertFalse(WardrobeItem.objects.exists())

    def test_invalid_input_does_not_create_empty_or_foreign_draft(self):
        for payload in ({}, {"name": "x" * 101}, {"category": self.foreign_category.pk}, {"name": "Draft", "photos": [png_upload(f"{i}.png") for i in range(6)]}):
            with self.subTest(keys=list(payload)):
                self.assertEqual(self.client.post(self.url, payload).status_code, 400)
                self.assertFalse(WardrobeItem.objects.exists())

    def test_stale_or_missing_version_and_wrong_id_do_not_overwrite(self):
        self.create_saved_draft()
        for data in ({"version": "outdated"}, {"version": ""}, {"draft_id": ""}, {"draft_id": self.draft.pk + 99}):
            with self.subTest(data=data):
                response = self.submit(**data)
                self.assertEqual(response.status_code, 409)
                self.assertEqual(response.json()["errors"]["__all__"][0]["code"], "draft_conflict")
                self.assert_original()
        self.client.force_login(self.other)
        self.assertEqual(self.submit().status_code, 409)
        self.assertFalse(WardrobeItem.objects.filter(owner=self.other).exists())
        self.assert_original()

    def test_removed_draft_id_does_not_create_a_replacement(self):
        response = self.client.post(self.url, {"draft_id": 999, "version": "old", "name": "Draft"})
        self.assertEqual(response.status_code, 409)
        self.assertFalse(WardrobeItem.objects.exists())

    def test_kept_photo_ids_and_files_survive_reordering_and_cleanup(self):
        self.create_saved_draft()
        with self.captureOnCommitCallbacks(execute=True):
            response = self.submit(delete_photos=[self.photos[0].pk], photos=[png_upload("new.png")])
            self.assertTrue(self.storage.exists(self.photos[0].image.name))
            self.assertTrue(WardrobePhotoCleanup.objects.filter(file_name=self.photos[0].image.name).exists())
        self.assertEqual(response.status_code, 200)
        result = response.json()["draft"]
        self.assertEqual([p["position"] for p in result["photos"]], [1, 2])
        self.assertEqual(result["photos"][0]["id"], self.photos[1].pk)
        self.assertFalse(self.storage.exists(self.photos[0].image.name))
        self.assertEqual((self.root / self.photos[1].image.name).read_bytes(), self.before[self.photos[1].image.name])
        self.assertFalse(WardrobePhotoCleanup.objects.exists())

    def test_foreign_photo_and_total_over_limit_do_not_change_draft(self):
        self.create_saved_draft(photos=5)
        foreign_item = WardrobeItem.objects.create(owner=self.other, name="Other")
        foreign_photo = WardrobeItemImage.objects.create(item=foreign_item, position=1, image=png_upload())
        for data in ({"delete_photos": [foreign_photo.pk]}, {"photos": [png_upload()]}):
            self.assertEqual(self.submit(**data).status_code, 400)
            self.assert_original()

    def test_failed_cleanup_is_persistent_and_command_retry_finishes_it(self):
        self.create_saved_draft()
        with patch.object(self.storage, "delete", side_effect=OSError("storage unavailable")):
            with self.assertLogs("apps.wardrobe.cleanup", level="ERROR"):
                with self.captureOnCommitCallbacks(execute=True):
                    response = self.submit(delete_photos=[self.photos[0].pk])
        self.assertEqual(response.status_code, 200)
        self.assertTrue(self.storage.exists(self.photos[0].image.name))
        self.assertTrue(WardrobePhotoCleanup.objects.filter(file_name=self.photos[0].image.name).exists())
        call_command("cleanup_wardrobe_photos", stdout=StringIO())
        self.assertFalse(self.storage.exists(self.photos[0].image.name))
        self.assertTrue(self.storage.exists(self.photos[1].image.name))
        self.assertFalse(WardrobePhotoCleanup.objects.exists())

    def test_database_failure_preserves_old_draft_and_queues_failed_new_cleanup(self):
        self.create_saved_draft()
        with patch.object(WardrobeItemImage, "save", side_effect=IntegrityError("insert failed")):
            with patch.object(self.storage, "delete", side_effect=OSError("storage unavailable")):
                with self.assertLogs("apps.wardrobe", level="ERROR"):
                    with self.captureOnCommitCallbacks(execute=True) as callbacks:
                        response = self.submit(delete_photos=[self.photos[0].pk], photos=[png_upload()])
        self.assertEqual(response.status_code, 500)
        self.assertEqual(callbacks, [])
        self.assert_original()
        pending = set(WardrobePhotoCleanup.objects.values_list("file_name", flat=True))
        self.assertEqual(len(pending), 1)
        self.assertTrue(pending.isdisjoint(self.before))
        call_command("cleanup_wardrobe_photos", stdout=StringIO())
        self.assertFalse(WardrobePhotoCleanup.objects.exists())
        self.assert_original()

    def test_partial_upload_failure_rolls_back_new_draft_and_cleans_first_file(self):
        original_save = self.storage.save
        calls = 0

        def fail_second(*args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError("second file failed")
            return original_save(*args, **kwargs)

        with patch.object(self.storage, "save", side_effect=fail_second):
            with self.assertLogs("apps.wardrobe.views", level="ERROR"):
                response = self.client.post(self.url, {"photos": [png_upload("one.png"), png_upload("two.png")]})
        self.assertEqual(response.status_code, 500)
        self.assertFalse(WardrobeItem.objects.exists())
        self.assertFalse(WardrobeItemImage.objects.exists())
        self.assertFalse(WardrobePhotoCleanup.objects.exists())
        self.assertFalse(any(path.is_file() for path in self.root.rglob("*")))
