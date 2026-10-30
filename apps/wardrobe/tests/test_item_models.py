import os
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, transaction
from django.test import TestCase, SimpleTestCase, override_settings

from apps.wardrobe.models import Category, WardrobeItem, WardrobeItemImage, wardrobe_photo_path
from apps.wardrobe.storage import PrivateWardrobeStorage
from apps.wardrobe.validators import MAX_PHOTO_SIZE, validate_photo_size


class ItemModelTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user(username="item-owner")
        self.category = Category.objects.get(owner=self.owner, name="Kaos")
        self.item = WardrobeItem.objects.create(
            owner=self.owner, name="Kaos Hitam", category=self.category
        )

    def test_category_deletion_preserves_item_and_images(self):
        image = WardrobeItemImage.objects.create(
            item=self.item, image="photos/example.png", position=1
        )
        self.category.delete()
        self.item.refresh_from_db()
        self.assertIsNone(self.item.category_id)
        self.assertTrue(WardrobeItemImage.objects.filter(pk=image.pk).exists())

    def test_five_slots_and_database_rejects_duplicate_or_out_of_range(self):
        for position in range(1, 6):
            WardrobeItemImage.objects.create(
                item=self.item, image=f"photos/{position}.png", position=position
            )
        for position in (0, 6, 1):
            with self.subTest(position=position):
                with self.assertRaises(IntegrityError), transaction.atomic():
                    WardrobeItemImage.objects.create(
                        item=self.item, image="photos/extra.png", position=position
                    )
        self.assertEqual(self.item.images.count(), 5)

    def test_same_name_is_allowed_for_multiple_items(self):
        WardrobeItem.objects.create(owner=self.owner, name=self.item.name)
        self.assertEqual(WardrobeItem.objects.filter(name=self.item.name).count(), 2)

    def test_image_extension_and_position_validation(self):
        image = WardrobeItemImage(
            item=self.item,
            image=SimpleUploadedFile("file.svg", b"<svg></svg>"),
            position=6,
        )
        with self.assertRaises(ValidationError) as raised:
            image.full_clean()
        self.assertIn("image", raised.exception.message_dict)
        self.assertIn("position", raised.exception.message_dict)


class PhotoStorageTests(SimpleTestCase):
    def test_size_limit_includes_exactly_five_million_bytes(self):
        validate_photo_size(SimpleNamespace(size=MAX_PHOTO_SIZE))
        with self.assertRaises(ValidationError):
            validate_photo_size(SimpleNamespace(size=MAX_PHOTO_SIZE + 1))

    def test_photo_names_are_random_and_drop_supplied_directories(self):
        first = wardrobe_photo_path(None, "../../original.PNG")
        second = wardrobe_photo_path(None, "../../original.PNG")
        self.assertNotEqual(first, second)
        self.assertRegex(first, r"^photos/[a-f0-9]{32}\.png$")

    def test_storage_has_no_public_url_and_uses_private_permissions(self):
        with TemporaryDirectory() as directory:
            with override_settings(WARDROBE_PRIVATE_ROOT=Path(directory)):
                storage = PrivateWardrobeStorage()
                name = storage.save("photos/example.txt", ContentFile(b"private-test"))
                self.assertTrue(Path(storage.path(name)).is_relative_to(Path(directory)))
                with storage.open(name) as stored:
                    self.assertEqual(stored.read(), b"private-test")
                with self.assertRaises(NotImplementedError):
                    storage.url(name)
                if os.name == "posix":
                    self.assertEqual(Path(storage.path(name)).stat().st_mode & 0o777, 0o600)
                    self.assertEqual(Path(storage.path(name)).parent.stat().st_mode & 0o777, 0o700)
                storage.delete(name)

    def test_storage_follows_overridden_root(self):
        storage = PrivateWardrobeStorage()
        with TemporaryDirectory() as first, TemporaryDirectory() as second:
            with override_settings(WARDROBE_PRIVATE_ROOT=Path(first)):
                self.assertEqual(Path(storage.location), Path(first))
            with override_settings(WARDROBE_PRIVATE_ROOT=Path(second)):
                self.assertEqual(Path(storage.location), Path(second))
