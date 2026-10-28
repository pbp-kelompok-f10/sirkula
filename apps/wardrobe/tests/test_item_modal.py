from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.wardrobe.models import Category, WardrobeItem, WardrobeItemImage
from .test_private_photos import png_upload


class ItemModalTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user(username="modal-owner")
        self.category = Category.objects.create(owner=self.owner, name="Kaos")
        self.other = get_user_model().objects.create_user(username="modal-other")
        self.foreign = Category.objects.create(owner=self.other, name="Kategori Privat Lain")
        self.client.force_login(self.owner)
        self.url = reverse("wardrobe:create_item")
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        settings = override_settings(WARDROBE_PRIVATE_ROOT=self.root)
        settings.enable()
        self.addCleanup(settings.disable)

    def submit(self, **changes):
        data = {"name": "Kaos Modal", "category": self.category.pk, "photos": [png_upload()]}
        data.update(changes)
        return self.client.post(self.url, data)

    def test_authenticated_modal_has_upload_action_and_private_category_choices(self):
        response = self.client.get(reverse("wardrobe:index"))
        self.assertContains(response, 'id="item-modal"')
        self.assertContains(response, f'action="{self.url}" enctype="multipart/form-data"')
        self.assertContains(response, 'name="photos" multiple required')
        self.assertContains(response, "Tambah Pakaian Baru")
        self.assertContains(response, "maksimal 5 MB per foto")
        self.assertNotContains(response, self.foreign.name)
        self.assertNotContains(response, ">Draft<")
        self.assertContains(response, 'wardrobe/js/wardrobe.js', count=1)

    def test_anonymous_has_no_upload_modal(self):
        self.client.logout()
        response = self.client.get(reverse("wardrobe:index"))
        self.assertNotContains(response, 'id="item-modal"')
        self.assertContains(response, 'disabled title="Silakan login untuk menambahkan pakaian"')

    def test_no_categories_explains_how_to_proceed(self):
        self.category.delete()
        response = self.client.get(reverse("wardrobe:index"))
        self.assertContains(response, 'data-no-categories="true"')
        self.assertContains(response, "Tambahkan kategori terlebih dahulu")

    def test_error_reopens_modal_retains_fields_and_explains_file_reselection(self):
        response = self.submit(photos=[])
        self.assertContains(response, "Tambahkan minimal satu foto pakaian.", status_code=400)
        self.assertContains(response, 'data-open-on-load="true"', status_code=400)
        self.assertContains(response, 'value="Kaos Modal"', status_code=400)
        self.assertContains(response, f'<option value="{self.category.pk}" selected>', status_code=400)
        self.assertContains(response, "Pilih ulang foto sebelum menyimpan lagi.", status_code=400)
        self.assertFalse(WardrobeItem.objects.exists())

    def test_field_errors_are_visible_and_foreign_category_is_rejected(self):
        response = self.submit(name=" ", category=self.foreign.pk)
        self.assertContains(response, "Nama pakaian wajib diisi.", status_code=400)
        self.assertContains(response, "Pilih kategori milik akunmu.", status_code=400)
        self.assertContains(response, 'id="item-name-errors"', status_code=400)
        self.assertContains(response, 'id="item-category-errors"', status_code=400)
        self.assertFalse(WardrobeItem.objects.exists())

    def test_six_photos_are_rejected_without_writing_files(self):
        response = self.submit(photos=[png_upload(f"{i}.png") for i in range(6)])
        self.assertContains(response, "Maksimal lima foto untuk setiap pakaian.", status_code=400)
        self.assertFalse(WardrobeItem.objects.exists())
        self.assertFalse(any(p.is_file() for p in self.root.rglob("*")))

    def test_storage_failure_renders_general_error_inside_modal(self):
        storage = WardrobeItemImage._meta.get_field("image").storage
        with patch.object(storage, "save", side_effect=OSError("Disk unavailable")):
            with self.assertLogs("apps.wardrobe.views", level="ERROR"):
                response = self.submit()
        self.assertContains(response, 'id="item-form-errors"', status_code=500)
        self.assertContains(response, "Pakaian gagal disimpan. Silakan coba lagi.", status_code=500)
        self.assertContains(response, 'data-open-on-load="true"', status_code=500)
        self.assertFalse(WardrobeItem.objects.exists())
