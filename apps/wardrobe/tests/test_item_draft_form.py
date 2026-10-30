from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from apps.wardrobe.forms import WardrobeItemDraftForm, WardrobeItemForm
from apps.wardrobe.models import Category, WardrobeItem, WardrobeItemImage
from .test_private_photos import png_upload


class ItemDraftFormTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user(username="draft-form-owner")
        self.other = get_user_model().objects.create_user(username="draft-form-other")
        self.category = Category.objects.create(owner=self.owner, name="Atasan")
        self.foreign_category = Category.objects.create(owner=self.other, name="Pribadi")

    def form(self, data=None, files=None, **kwargs):
        return WardrobeItemDraftForm(
            data={} if data is None else data,
            files=files,
            owner=self.owner,
            **kwargs,
        )

    def draft(self, owner=None):
        return WardrobeItem.objects.create(
            owner=owner or self.owner, status=WardrobeItem.Status.DRAFT,
        )

    def photos(self, item, count):
        return [
            WardrobeItemImage.objects.create(
                item=item, position=i, image=f"photos/{item.pk}-{i}.png",
            )
            for i in range(1, count + 1)
        ]

    def test_each_valid_partial_input_is_accepted(self):
        for data, files in (
            ({"name": "  Kaos Biru  "}, None),
            ({"category": self.category.pk}, None),
            ({}, {"photos": [png_upload()]}),
        ):
            with self.subTest(data=data, with_photo=files is not None):
                form = self.form(data, files)
                self.assertTrue(form.is_valid(), form.errors)
                self.assertEqual(form.instance.owner_id, self.owner.pk)
                self.assertEqual(form.instance.status, WardrobeItem.Status.DRAFT)
        self.assertFalse(WardrobeItem.objects.exists())

    def test_empty_whitespace_and_overlong_name_are_rejected(self):
        for name in ("", "   ", "x" * 101):
            with self.subTest(name=name):
                form = self.form({"name": name})
                self.assertFalse(form.is_valid())
                self.assertIn("name" if len(name) > 100 else "__all__", form.errors)

    def test_foreign_category_and_injected_owner_status_are_not_accepted(self):
        form = self.form({"name": "Draft", "category": self.foreign_category.pk})
        self.assertFalse(form.is_valid())
        self.assertIn("category", form.errors)
        form = self.form({"name": "Draft", "owner": self.other.pk, "status": "active"})
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.instance.owner_id, self.owner.pk)
        self.assertEqual(form.instance.status, WardrobeItem.Status.DRAFT)

    def test_form_rejects_anonymous_foreign_or_active_instance(self):
        from django.contrib.auth.models import AnonymousUser
        for owner in (None, AnonymousUser()):
            with self.subTest(owner=owner), self.assertRaises(ValueError):
                WardrobeItemDraftForm(owner=owner)
        foreign = self.draft(owner=self.other)
        active = WardrobeItem.objects.create(owner=self.owner, name="Aktif")
        for item in (foreign, active):
            with self.subTest(item=item.pk), self.assertRaises(ValueError):
                self.form(instance=item)
        active.refresh_from_db()
        self.assertEqual(active.status, WardrobeItem.Status.ACTIVE)

    def test_saved_photos_can_be_kept_without_reupload(self):
        item = self.draft()
        photos = self.photos(item, 2)
        form = self.form(instance=item)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["photos"], [])
        self.assertEqual(list(item.images.values_list("pk", flat=True)), [p.pk for p in photos])

    def test_removing_all_photos_requires_other_content_and_does_not_delete_rows(self):
        item = self.draft()
        photos = self.photos(item, 1)
        data = {"delete_photos": [photos[0].pk]}
        form = self.form(data, instance=item)
        self.assertFalse(form.is_valid())
        self.assertIn("__all__", form.errors)
        form = self.form({**data, "name": "Lanjut nanti"}, instance=item)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertTrue(WardrobeItemImage.objects.filter(pk=photos[0].pk).exists())

    def test_foreign_photo_cannot_be_selected_for_removal(self):
        item = self.draft()
        foreign_photo = self.photos(self.draft(owner=self.other), 1)[0]
        form = self.form({"name": "Draft", "delete_photos": [foreign_photo.pk]}, instance=item)
        self.assertFalse(form.is_valid())
        self.assertIn("delete_photos", form.errors)

    def test_total_limit_counts_kept_and_new_photos(self):
        item = self.draft()
        photos = self.photos(item, 5)
        form = self.form(files={"photos": [png_upload()]}, instance=item)
        self.assertFalse(form.is_valid())
        self.assertIn("photos", form.errors)
        form = self.form({"delete_photos": [photos[0].pk]}, {"photos": [png_upload()]}, instance=item)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(item.images.count(), 5)
        form = self.form({"name": "Draft"}, {"photos": [png_upload(f"{i}.png") for i in range(6)]})
        self.assertFalse(form.is_valid())
        self.assertIn("photos", form.errors)

    def test_invalid_format_corrupt_and_oversize_files_are_rejected(self):
        gif = png_upload()
        gif.name = "not-allowed.gif"
        large = png_upload()
        large.size = 5_000_001
        corrupt = SimpleUploadedFile("broken.png", b"not an image", content_type="image/png")
        for photo in (gif, large, corrupt):
            with self.subTest(name=photo.name):
                form = self.form({"name": "Draft"}, {"photos": [photo]})
                self.assertFalse(form.is_valid())
                self.assertIn("photos", form.errors)

    def test_active_item_form_still_requires_all_fields(self):
        self.form({"name": "Draft"}).is_valid()
        form = WardrobeItemForm(data={}, owner=self.owner)
        self.assertFalse(form.is_valid())
        for name in ("name", "category", "photos"):
            self.assertTrue(form.fields[name].required)
            self.assertIn(name, form.errors)
