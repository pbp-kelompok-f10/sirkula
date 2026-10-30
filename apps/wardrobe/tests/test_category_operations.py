from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from apps.wardrobe.forms import CategoryForm
from apps.wardrobe.models import (
    Category,
    WardrobeItem,
    WardrobeItemImage,
    WardrobePhotoCleanup,
)
from .test_private_photos import png_upload


class CategoryOperationTests(TestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        settings = override_settings(WARDROBE_PRIVATE_ROOT=Path(directory.name))
        settings.enable()
        self.addCleanup(settings.disable)

        self.owner = get_user_model().objects.create_user(username="category-operations-owner")
        self.other = get_user_model().objects.create_user(username="category-operations-other")
        self.category = Category.objects.create(owner=self.owner, name="Atasan")
        self.duplicate = Category.objects.get(owner=self.owner, name="Outer")
        self.foreign = Category.objects.create(owner=self.other, name="Pribadi")
        self.item = WardrobeItem.objects.create(
            owner=self.owner, category=self.category, name="Kaos"
        )
        self.photo = WardrobeItemImage.objects.create(
            item=self.item, image=png_upload(), position=1
        )
        self.storage = self.photo.image.storage
        self.photo_name = self.photo.image.name
        self.photo_bytes = (Path(directory.name) / self.photo_name).read_bytes()
        self.edit_url = reverse(
            "wardrobe:update_category", kwargs={"category_id": self.category.pk}
        )
        self.delete_url = reverse(
            "wardrobe:delete_category", kwargs={"category_id": self.category.pk}
        )
        self.client.force_login(self.owner)

    def assert_photo_unchanged(self):
        self.photo.refresh_from_db()
        self.assertEqual(self.photo.item_id, self.item.pk)
        self.assertEqual(self.photo.position, 1)
        self.assertEqual(self.photo.image.name, self.photo_name)
        with self.storage.open(self.photo_name, "rb") as image:
            self.assertEqual(image.read(), self.photo_bytes)
        self.assertFalse(WardrobePhotoCleanup.objects.exists())

    def test_edit_preserves_id_owner_relationship_and_active_filter(self):
        Category.objects.filter(owner=self.owner, name="Kemeja").delete()
        response = self.client.post(self.edit_url, {
            "name": "  Kemeja  ",
            "owner": self.other.pk,
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {
            "ok": True,
            "category": {"id": self.category.pk, "name": "Kemeja"},
        })
        self.assertIn("no-store", response["Cache-Control"])
        self.assertIn("Cookie", response["Vary"])
        self.category.refresh_from_db()
        self.assertEqual(self.category.owner_id, self.owner.pk)
        self.item.refresh_from_db()
        self.assertEqual(self.item.category_id, self.category.pk)
        detail_url = reverse("wardrobe:item_detail", kwargs={"item_id": self.item.pk})
        detail = self.client.get(detail_url).json()["item"]
        self.assertEqual(detail["category"]["name"], "Kemeja")
        response = self.client.get(reverse("wardrobe:index"), {"category": self.category.pk})
        self.assertEqual(response.context["active_category_id"], self.category.pk)
        self.assertIn(self.item, list(response.context["clothes"]))
        self.assert_photo_unchanged()

    def test_same_name_and_other_owner_name_are_allowed(self):
        self.assertEqual(self.client.post(self.edit_url, {"name": "Atasan"}).status_code, 200)
        self.assertEqual(self.client.post(self.edit_url, {"name": "Pribadi"}).status_code, 200)
        self.assertEqual(Category.objects.filter(name="Pribadi").count(), 2)
        self.foreign.refresh_from_db()
        self.assertEqual(self.foreign.owner_id, self.other.pk)
        self.assert_photo_unchanged()

    def test_invalid_and_duplicate_names_return_field_errors(self):
        for name in ("", " ", "x" * 101, "  OUTER  "):
            with self.subTest(name=name):
                response = self.client.post(self.edit_url, {"name": name})
                self.assertEqual(response.status_code, 400)
                self.assertFalse(response.json()["ok"])
                self.assertIn("name", response.json()["errors"])
                self.category.refresh_from_db()
                self.assertEqual(self.category.name, "Atasan")
        self.assert_photo_unchanged()

    def test_other_owner_anonymous_and_missing_categories_are_rejected(self):
        for user in (self.other, None):
            if user is None:
                self.client.logout()
            else:
                self.client.force_login(user)
            for url in (self.edit_url, self.delete_url):
                with self.subTest(user=user, url=url):
                    self.assertEqual(self.client.post(url, {"name": "Diubah"}).status_code, 404)
        self.client.force_login(self.owner)
        for route in ("update_category", "delete_category"):
            missing_url = reverse(f"wardrobe:{route}", kwargs={"category_id": 999999})
            self.assertEqual(self.client.post(missing_url, {"name": "Diubah"}).status_code, 404)
        self.category.refresh_from_db()
        self.assertEqual(self.category.name, "Atasan")
        self.assert_photo_unchanged()

    def test_only_post_is_allowed_and_csrf_is_required(self):
        protected = Client(enforce_csrf_checks=True)
        protected.force_login(self.owner)
        for url in (self.edit_url, self.delete_url):
            for method in ("get", "head", "put", "patch", "delete"):
                with self.subTest(url=url, method=method):
                    self.assertEqual(getattr(self.client, method)(url).status_code, 405)
            self.assertEqual(protected.post(url, {"name": "Diubah"}).status_code, 403)
        self.category.refresh_from_db()
        self.assertEqual(self.category.name, "Atasan")
        self.assert_photo_unchanged()

    def test_delete_keeps_item_photo_and_file_and_item_appears_in_all(self):
        category_id = self.category.pk
        item_id = self.item.pk
        photo_id = self.photo.pk
        with patch.object(self.storage, "delete") as delete_file:
            response = self.client.post(self.delete_url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"ok": True, "category": {"id": category_id}})
        self.assertFalse(Category.objects.filter(pk=category_id).exists())
        self.assertTrue(Category.objects.filter(pk=self.foreign.pk).exists())
        self.item.refresh_from_db()
        self.assertEqual(self.item.pk, item_id)
        self.assertIsNone(self.item.category_id)
        self.assertEqual(self.item.images.get().pk, photo_id)
        delete_file.assert_not_called()
        self.assert_photo_unchanged()
        response = self.client.get(reverse("wardrobe:index"))
        self.assertIsNone(response.context["active_category_id"])
        self.assertIn(self.item, list(response.context["clothes"]))
        detail_url = reverse("wardrobe:item_detail", kwargs={"item_id": item_id})
        detail = self.client.get(detail_url).json()["item"]
        self.assertIsNone(detail["category"])
        self.assertEqual([photo["id"] for photo in detail["photos"]], [photo_id])

    def test_delete_failure_restores_category_relationship_and_photo(self):
        original_delete = Category.delete

        def fail_after_delete(category, *args, **kwargs):
            original_delete(category, *args, **kwargs)
            raise IntegrityError("simulated category delete failure")

        with self.assertLogs("apps.wardrobe.views", level="ERROR"):
            with patch.object(Category, "delete", new=fail_after_delete):
                response = self.client.post(self.delete_url)
        self.assertEqual(response.status_code, 500)
        self.assertIn("__all__", response.json()["errors"])
        self.category.refresh_from_db()
        self.assertEqual(self.category.name, "Atasan")
        self.item.refresh_from_db()
        self.assertEqual(self.item.category_id, self.category.pk)
        self.assert_photo_unchanged()

    def test_unexpected_edit_save_failure_does_not_change_category(self):
        with self.assertLogs("apps.wardrobe.views", level="ERROR"):
            with patch.object(Category, "save", side_effect=IntegrityError("simulated edit failure")):
                response = self.client.post(self.edit_url, {"name": "Baru"})
        self.assertEqual(response.status_code, 500)
        self.assertIn("__all__", response.json()["errors"])
        self.category.refresh_from_db()
        self.assertEqual(self.category.name, "Atasan")
        self.assert_photo_unchanged()

    def test_duplicate_at_database_save_returns_field_error(self):
        # Simulasikan form lolos sebelum nama duplikat terdeteksi oleh database.
        with patch.object(CategoryForm, "clean_name", return_value="Outer"):
            response = self.client.post(self.edit_url, {"name": "Outer"})
        self.assertEqual(response.status_code, 400)
        self.assertIn("name", response.json()["errors"])
        self.category.refresh_from_db()
        self.assertEqual(self.category.name, "Atasan")
        self.assertEqual(Category.objects.filter(owner=self.owner, name="Outer").count(), 1)
        self.assert_photo_unchanged()

    def test_empty_category_can_be_deleted_without_affecting_clothing(self):
        url = reverse("wardrobe:delete_category", kwargs={"category_id": self.duplicate.pk})
        self.assertEqual(self.client.post(url).status_code, 200)
        self.assertFalse(Category.objects.filter(pk=self.duplicate.pk).exists())
        self.item.refresh_from_db()
        self.assertEqual(self.item.category_id, self.category.pk)
        self.assert_photo_unchanged()
