from pathlib import Path
from tempfile import TemporaryDirectory

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.wardrobe.models import Category, WardrobeItem, WardrobeItemImage
from .test_private_photos import png_upload


class CurrentDraftTests(TestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        settings = override_settings(WARDROBE_PRIVATE_ROOT=self.root)
        settings.enable()
        self.addCleanup(settings.disable)
        self.owner = get_user_model().objects.create_user(username="current-draft-owner")
        self.other = get_user_model().objects.create_user(username="current-draft-other")
        self.category = Category.objects.create(owner=self.owner, name="Atasan")
        self.draft = WardrobeItem.objects.create(
            owner=self.owner, category=self.category,
            name="Draft Rahasia", status=WardrobeItem.Status.DRAFT,
        )
        self.active = WardrobeItem.objects.create(
            owner=self.owner, category=self.category, name="Pakaian Aktif",
        )
        self.second_photo = WardrobeItemImage.objects.create(
            item=self.draft, image=png_upload("second.png"), position=2,
        )
        self.first_photo = WardrobeItemImage.objects.create(
            item=self.draft, image=png_upload("first.png"), position=1,
        )
        self.url = reverse("wardrobe:current_draft")
        self.client.force_login(self.owner)

    def test_owner_receives_draft_with_ordered_private_urls_and_version(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        payload = response.json()["draft"]
        self.assertEqual(payload["id"], self.draft.pk)
        self.assertEqual(payload["name"], self.draft.name)
        self.assertEqual(payload["category"], {"id": self.category.pk, "name": self.category.name})
        self.assertEqual(payload["version"], self.draft.updated_at.isoformat())
        self.assertEqual([p["id"] for p in payload["photos"]], [self.first_photo.pk, self.second_photo.pk])
        for data, photo in zip(payload["photos"], (self.first_photo, self.second_photo)):
            self.assertEqual(data["url"], reverse("wardrobe:item_photo", kwargs={"photo_id": photo.pk}))
            self.assertNotContains(response, photo.image.name)
        self.assertNotContains(response, str(self.root))
        self.assertNotIn("owner", payload)
        self.assertIn("no-store", response["Cache-Control"])
        self.assertIn("Cookie", response["Vary"])

    def test_other_owner_only_receives_own_draft(self):
        foreign = WardrobeItem.objects.create(
            owner=self.other, name="Draft Lain", status=WardrobeItem.Status.DRAFT,
        )
        self.client.force_login(self.other)
        response = self.client.get(self.url)
        self.assertEqual(response.json()["draft"]["id"], foreign.pk)
        self.assertNotContains(response, self.draft.name)

    def test_no_draft_returns_null_without_creating_anything(self):
        self.client.force_login(self.other)
        before = WardrobeItem.objects.count()
        self.assertEqual(self.client.get(self.url).json(), {"ok": True, "draft": None})
        self.assertEqual(WardrobeItem.objects.count(), before)

    def test_anonymous_and_post_are_rejected(self):
        self.assertEqual(self.client.post(self.url).status_code, 405)
        response = self.client.head(self.url)
        self.assertEqual(response.status_code, 200)
        self.client.logout()
        self.assertEqual(self.client.get(self.url).status_code, 404)

    def test_deleted_category_and_empty_photo_list_are_supported(self):
        self.category.delete()
        self.draft.images.all().delete()
        payload = self.client.get(self.url).json()["draft"]
        self.assertIsNone(payload["category"])
        self.assertEqual(payload["photos"], [])

    def test_draft_is_hidden_in_all_and_category_filter(self):
        for params in ({}, {"category": self.category.pk}):
            with self.subTest(params=params):
                response = self.client.get(reverse("wardrobe:index"), params)
                self.assertContains(response, self.active.name)
                self.assertNotContains(response, self.draft.name)

    def test_active_item_endpoints_reject_draft_without_changing_it(self):
        before = list(self.draft.images.values_list("pk", "image", "position"))
        for route, method in (("item_detail", "get"), ("update_item", "post"), ("delete_item", "post")):
            with self.subTest(route=route):
                url = reverse(f"wardrobe:{route}", kwargs={"item_id": self.draft.pk})
                self.assertEqual(getattr(self.client, method)(url).status_code, 404)
        self.draft.refresh_from_db()
        self.assertEqual(self.draft.status, WardrobeItem.Status.DRAFT)
        self.assertEqual(list(self.draft.images.values_list("pk", "image", "position")), before)
        self.assertTrue(all((self.root / name).is_file() for _, name, _ in before))

    def test_draft_photo_is_private_and_available_to_owner(self):
        url = reverse("wardrobe:item_photo", kwargs={"photo_id": self.first_photo.pk})
        response = self.client.get(url)
        try:
            self.assertEqual(response.status_code, 200)
            self.assertTrue(b"".join(response.streaming_content).startswith(b"\x89PNG"))
        finally:
            response.close()
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(url).status_code, 404)
        self.client.logout()
        self.assertEqual(self.client.get(url).status_code, 404)
