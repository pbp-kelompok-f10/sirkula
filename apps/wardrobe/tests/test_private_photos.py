from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from PIL import Image
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.wardrobe.models import Category, WardrobeItem, WardrobeItemImage


def png_upload(name="test.png"):
    content = BytesIO()
    Image.new("RGB", (8, 8), "green").save(content, format="PNG")
    return SimpleUploadedFile(name, content.getvalue(), content_type="image/png")


class PrivatePhotoTests(TestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.directory = Path(directory.name)
        settings = override_settings(WARDROBE_PRIVATE_ROOT=self.directory)
        settings.enable()
        self.addCleanup(settings.disable)
        self.owner = get_user_model().objects.create_user(username="photo-owner")
        self.other = get_user_model().objects.create_user(username="photo-other")
        self.category = Category.objects.create(owner=self.owner, name="Kaos")
        self.item = WardrobeItem.objects.create(
            owner=self.owner, category=self.category, name="Kaos Hijau"
        )
        self.photo = WardrobeItemImage.objects.create(
            item=self.item, image=png_upload(), position=1
        )
        self.url = reverse("wardrobe:item_photo", kwargs={"photo_id": self.photo.pk})
        self.client.force_login(self.owner)

    def test_owner_receives_photo_with_private_response_headers(self):
        response = self.client.get(self.url)
        try:
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response["Content-Type"], "image/png")
            self.assertTrue(b"".join(response.streaming_content).startswith(b"\x89PNG"))
            self.assertIn("private", response["Cache-Control"])
            self.assertIn("no-store", response["Cache-Control"])
            self.assertIn("Cookie", response["Vary"])
            self.assertEqual(response["X-Content-Type-Options"], "nosniff")
            self.assertEqual(response["Cross-Origin-Resource-Policy"], "same-origin")
            self.assertIn("inline", response["Content-Disposition"])
            self.assertNotIn(self.photo.image.name, response["Content-Disposition"])
        finally:
            response.close()

    def test_other_user_and_anonymous_are_denied_before_file_is_opened(self):
        storage = WardrobeItemImage._meta.get_field("image").storage
        for user in (self.other, None):
            with self.subTest(user=user):
                if user is None:
                    self.client.logout()
                else:
                    self.client.force_login(user)
                with patch.object(storage, "open") as open_file:
                    response = self.client.get(self.url)
                self.assertEqual(response.status_code, 404)
                open_file.assert_not_called()

    def test_missing_photo_or_missing_file_returns_404(self):
        missing_url = reverse("wardrobe:item_photo", kwargs={"photo_id": self.photo.pk + 999})
        self.assertEqual(self.client.get(missing_url).status_code, 404)
        self.photo.image.storage.delete(self.photo.image.name)
        self.assertEqual(self.client.get(self.url).status_code, 404)

    def test_unsupported_file_type_is_not_opened(self):
        WardrobeItemImage.objects.filter(pk=self.photo.pk).update(image="photos/file.svg")
        storage = WardrobeItemImage._meta.get_field("image").storage
        with patch.object(storage, "open") as open_file:
            self.assertEqual(self.client.get(self.url).status_code, 404)
        open_file.assert_not_called()

    def test_only_get_and_head_are_allowed(self):
        response = self.client.head(self.url)
        try:
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response["Content-Type"], "image/png")
        finally:
            response.close()
        self.assertEqual(self.client.post(self.url).status_code, 405)

    def test_card_uses_first_photo_endpoint_and_not_storage_url(self):
        WardrobeItemImage.objects.create(item=self.item, image=png_upload(), position=2)
        response = self.client.get(reverse("wardrobe:index"))
        self.assertContains(response, f'src="{self.url}"')
        self.assertNotContains(response, self.photo.image.name)
        self.client.force_login(self.other)
        response = self.client.get(reverse("wardrobe:index"))
        self.assertNotContains(response, self.item.name)
        self.assertNotContains(response, self.url)

    def test_created_item_can_be_viewed_through_private_photo_endpoint(self):
        response = self.client.post(reverse("wardrobe:create_item"), {
            "name": "Kemeja Baru", "category": self.category.pk,
            "photos": [png_upload("first.png"), png_upload("second.png")],
            "owner": self.other.pk,
        })
        self.assertRedirects(response, reverse("wardrobe:index"))
        item = WardrobeItem.objects.get(name="Kemeja Baru")
        self.assertEqual(item.owner, self.owner)
        self.assertEqual(item.images.count(), 2)
        photo_url = reverse("wardrobe:item_photo", kwargs={"photo_id": item.images.first().pk})
        response = self.client.get(photo_url)
        try:
            self.assertEqual(response.status_code, 200)
        finally:
            response.close()
        self.assertContains(self.client.get(reverse("wardrobe:index")), photo_url)

    def test_failure_on_second_file_rolls_back_and_removes_first_file(self):
        storage = WardrobeItemImage._meta.get_field("image").storage
        save = storage.save
        calls = 0

        def fail_second(*args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError("Simulated storage failure")
            return save(*args, **kwargs)

        before = set(self.directory.rglob("*"))
        with patch.object(storage, "save", side_effect=fail_second):
            with self.assertLogs("apps.wardrobe.views", level="ERROR"):
                response = self.client.post(reverse("wardrobe:create_item"), {
                    "name": "Gagal Disimpan", "category": self.category.pk,
                    "photos": [png_upload("one.png"), png_upload("two.png")],
                })
        self.assertEqual(response.status_code, 500)
        self.assertFalse(WardrobeItem.objects.filter(name="Gagal Disimpan").exists())
        self.assertEqual({p for p in self.directory.rglob("*") if p.is_file()},
                         {p for p in before if p.is_file()})
