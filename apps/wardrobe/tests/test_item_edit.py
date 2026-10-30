from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from apps.wardrobe.forms import WardrobeItemEditForm, WardrobeItemForm
from apps.wardrobe.models import Category, WardrobeItem, WardrobeItemImage
from .test_private_photos import png_upload


class ItemEditTests(TestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        settings = override_settings(WARDROBE_PRIVATE_ROOT=self.root)
        settings.enable()
        self.addCleanup(settings.disable)
        self.owner = get_user_model().objects.create_user(username="edit-owner")
        self.other = get_user_model().objects.create_user(username="edit-other")
        self.category = Category.objects.get(owner=self.owner, name="Kaos")
        self.second_category = Category.objects.get(owner=self.owner, name="Outer")
        self.foreign_category = Category.objects.create(owner=self.other, name="Kategori Rahasia")
        self.item = WardrobeItem.objects.create(owner=self.owner, name="Kaos Awal", category=self.category)
        self.photos = [
            WardrobeItemImage.objects.create(item=self.item, image=png_upload(f"{i}.png"), position=i)
            for i in range(1, 6)
        ]
        self.storage = WardrobeItemImage._meta.get_field("image").storage
        self.before = {p.image.name: (self.root / p.image.name).read_bytes() for p in self.photos}
        self.url = reverse("wardrobe:update_item", kwargs={"item_id": self.item.pk})
        self.client.force_login(self.owner)

    def submit(self, **changes):
        data = {"name": "Kaos Diubah", "category": self.category.pk}
        data.update(changes)
        return self.client.post(self.url, data)

    def assert_original(self):
        self.item.refresh_from_db()
        self.assertEqual(self.item.name, "Kaos Awal")
        self.assertEqual(self.item.category_id, self.category.pk)
        self.assertEqual(list(self.item.images.values_list("id", "position")), [(p.pk, p.position) for p in self.photos])
        files = {str(p.relative_to(self.root)): p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        self.assertEqual(files, self.before)

    def test_edit_name_category_without_upload_preserves_photo_ids(self):
        response = self.submit(category=self.second_category.pk)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"ok": True, "item": {"id": self.item.pk}})
        self.item.refresh_from_db()
        self.assertEqual(self.item.name, "Kaos Diubah")
        self.assertEqual(self.item.category_id, self.second_category.pk)
        self.assertEqual(list(self.item.images.values_list("pk", flat=True)), [p.pk for p in self.photos])
        self.assertTrue(all(self.storage.exists(name) for name in self.before))

    def test_replace_and_delete_files_only_after_commit(self):
        deleted = [self.photos[0], self.photos[2]]
        with self.captureOnCommitCallbacks(execute=True) as callbacks:
            response = self.submit(delete_photos=[p.pk for p in deleted], photos=[png_upload("new.png")])
            self.assertEqual(response.status_code, 200)
            for photo in deleted:
                self.assertTrue(self.storage.exists(photo.image.name))
        self.assertEqual(len(callbacks), 1)
        self.assertEqual(list(self.item.images.values_list("position", flat=True)), [1, 2, 3, 4])
        self.assertEqual(list(self.item.images.values_list("pk", flat=True))[:3], [self.photos[i].pk for i in [1, 3, 4]])
        for photo in deleted:
            self.assertFalse(self.storage.exists(photo.image.name))
        self.assertTrue(all(self.storage.exists(p.image.name) for p in self.item.images.all()))

    def test_replace_all_photos_with_one(self):
        with self.captureOnCommitCallbacks(execute=True):
            response = self.submit(delete_photos=[p.pk for p in self.photos], photos=[png_upload()])
        self.assertEqual(response.status_code, 200)
        photo = self.item.images.get()
        self.assertEqual(photo.position, 1)
        self.assertNotIn(photo.pk, [p.pk for p in self.photos])
        self.assertTrue(self.storage.exists(photo.image.name))
        self.assertTrue(all(not self.storage.exists(name) for name in self.before))

    def test_storage_failure_after_first_upload_restores_original(self):
        original_save = self.storage.save
        calls = 0

        def fail_second(*args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError("simulated storage failure")
            return original_save(*args, **kwargs)

        with self.assertLogs("apps.wardrobe.views", level="ERROR"):
            with patch.object(self.storage, "save", side_effect=fail_second):
                response = self.submit(delete_photos=[p.pk for p in self.photos[:2]], photos=[png_upload("a.png"), png_upload("b.png")])
        self.assertEqual(response.status_code, 500)
        self.assertIn("__all__", response.json()["errors"])
        self.assert_original()

    def test_database_failure_after_old_rows_deleted_rolls_back_and_cleans_new_files(self):
        original_save = WardrobeItemImage.save

        def fail_new(photo, *args, **kwargs):
            if photo.pk is None:
                raise IntegrityError("simulated database failure")
            return original_save(photo, *args, **kwargs)

        with self.captureOnCommitCallbacks(execute=True) as callbacks:
            with self.assertLogs("apps.wardrobe.views", level="ERROR"):
                with patch.object(WardrobeItemImage, "save", new=fail_new):
                    response = self.submit(delete_photos=[self.photos[0].pk], photos=[png_upload()])
        self.assertEqual(response.status_code, 500)
        self.assertEqual(callbacks, [])
        self.assert_original()

    def test_cleanup_old_file_failure_does_not_remove_new_files(self):
        original_delete = self.storage.delete
        old_name = self.photos[0].image.name

        def fail_old(name):
            if name == old_name:
                raise OSError("simulated deletion failure")
            return original_delete(name)

        with self.assertLogs("apps.wardrobe.cleanup", level="ERROR"):
            with patch.object(self.storage, "delete", side_effect=fail_old):
                with self.captureOnCommitCallbacks(execute=True):
                    response = self.submit(delete_photos=[self.photos[0].pk], photos=[png_upload()])
        self.assertEqual(response.status_code, 200)
        self.assertTrue(self.storage.exists(old_name))
        self.assertFalse(self.item.images.filter(pk=self.photos[0].pk).exists())
        self.assertTrue(all(self.storage.exists(p.image.name) for p in self.item.images.all()))

    def test_six_total_photos_rejected(self):
        response = self.submit(photos=[png_upload()])
        self.assertEqual(response.status_code, 400)
        self.assertIn("photos", response.json()["errors"])
        self.assert_original()

    def test_deleting_all_without_replacement_rejected(self):
        response = self.submit(delete_photos=[p.pk for p in self.photos])
        self.assertEqual(response.status_code, 400)
        self.assertIn("photos", response.json()["errors"])
        self.assert_original()

    def test_foreign_category_rejected(self):
        response = self.submit(category=self.foreign_category.pk)
        self.assertEqual(response.status_code, 400)
        self.assertIn("category", response.json()["errors"])
        self.assert_original()

    def test_foreign_and_same_owner_other_item_photos_rejected(self):
        for owner, category in [(self.other, self.foreign_category), (self.owner, self.category)]:
            with self.subTest(owner=owner.pk):
                item = WardrobeItem.objects.create(owner=owner, name="Lain", category=category)
                photo = WardrobeItemImage.objects.create(item=item, image="photos/other.png", position=1)
                response = self.submit(delete_photos=[photo.pk])
                self.assertEqual(response.status_code, 400)
                self.assertIn("delete_photos", response.json()["errors"])
        self.assert_original()

    def test_other_user_and_anonymous_denied_before_file_write(self):
        for owner in [self.other, None]:
            with self.subTest(owner=owner):
                if owner:
                    self.client.force_login(owner)
                else:
                    self.client.logout()
                with patch.object(self.storage, "save") as save:
                    self.assertEqual(self.submit().status_code, 404)
                    save.assert_not_called()
        self.assert_original()

    def test_missing_item_and_get(self):
        missing = reverse("wardrobe:update_item", kwargs={"item_id": self.item.pk + 999})
        self.assertEqual(self.client.post(missing, {}).status_code, 404)
        self.assertEqual(self.client.get(self.url).status_code, 405)
        self.assert_original()

    def test_csrf_is_required(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.owner)
        self.assertEqual(client.post(self.url, {"name": "Ubah", "category": self.category.pk}).status_code, 403)
        self.assert_original()

    def test_invalid_name_oversized_and_corrupt_uploads(self):
        cases = [
            {"name": " "},
            {"photos": [SimpleUploadedFile("large.png", b"x" * 5_000_001, content_type="image/png")]},
            {"photos": [SimpleUploadedFile("bad.png", b"invalid", content_type="image/png")]},
        ]
        for changes in cases:
            with self.subTest(changes=list(changes)):
                response = self.submit(delete_photos=[self.photos[0].pk], **changes)
                self.assertEqual(response.status_code, 400)
                self.assert_original()

    def test_deleted_category_keeps_item_but_category_required_on_save(self):
        self.category.delete()
        self.item.refresh_from_db()
        self.assertIsNone(self.item.category_id)
        self.assertEqual(self.submit(category="").status_code, 400)
        self.assertEqual(self.item.images.count(), 5)
        self.assertTrue(all(self.storage.exists(name) for name in self.before))
        self.assertEqual(self.submit(category=self.second_category.pk).status_code, 200)

    def test_create_still_requires_photos_after_edit_form_initialized(self):
        WardrobeItemEditForm(owner=self.owner, instance=self.item)
        form = WardrobeItemForm({"name": "Baru", "category": self.category.pk}, owner=self.owner)
        self.assertFalse(form.is_valid())
        self.assertTrue(form.fields["photos"].required)
        self.assertIn("photos", form.errors)

    def test_modal_is_private_and_filters_remain_active_after_edit(self):
        index = reverse("wardrobe:index")
        filtered_url = f"{index}?category={self.category.pk}"
        response = self.client.get(filtered_url)
        self.assertContains(response, 'id="item-edit-modal"')
        self.assertContains(response, f'data-item-edit-url="{self.url}"')
        self.assertContains(response, 'id="cancel-item-edit"')
        self.assertContains(response, 'wardrobe/js/item-edit.js', count=1)
        self.assertNotContains(response, self.foreign_category.name)
        self.assertEqual(response.context["active_category_id"], self.category.pk)
        self.assertEqual(self.submit(category=self.second_category.pk).status_code, 200)
        response = self.client.get(filtered_url)
        self.assertEqual(response.context["active_category_id"], self.category.pk)
        self.assertNotContains(response, 'data-item-edit-url=')
        self.client.logout()
        self.assertNotContains(self.client.get(index), 'id="item-edit-modal"')
