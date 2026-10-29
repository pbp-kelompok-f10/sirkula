from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.wardrobe.models import Category, WardrobeItem, WardrobeItemImage


class ItemDetailTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = get_user_model().objects.create_user(username="detail-owner")
        cls.other = get_user_model().objects.create_user(username="detail-other")
        cls.category = Category.objects.create(owner=cls.owner, name="Atasan")
        cls.item = WardrobeItem.objects.create(owner=cls.owner, name="Kaos Detail", category=cls.category)
        cls.photos = {}
        for position in (3, 1, 2):
            cls.photos[position] = WardrobeItemImage.objects.create(
                item=cls.item, position=position, image=f"photos/private-detail-{position}.png"
            )
        cls.foreign = WardrobeItem.objects.create(owner=cls.other, name="Pakaian Rahasia Lain")

    def setUp(self):
        self.client.force_login(self.owner)
        self.url = reverse("wardrobe:item_detail", kwargs={"item_id": self.item.pk})

    def test_owner_receives_all_photos_in_position_order(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        data = response.json()["item"]
        self.assertEqual(data["id"], self.item.pk)
        self.assertEqual(data["name"], self.item.name)
        self.assertEqual(data["category"], {"id": self.category.pk, "name": self.category.name})
        self.assertEqual([p["position"] for p in data["photos"]], [1, 2, 3])
        for photo in data["photos"]:
            self.assertEqual(photo["url"], reverse("wardrobe:item_photo", kwargs={"photo_id": self.photos[photo["position"]].pk}))

    def test_other_user_and_anonymous_cannot_access_detail(self):
        for user in (self.other, None):
            with self.subTest(user=user):
                if user is None:
                    self.client.logout()
                else:
                    self.client.force_login(user)
                response = self.client.get(self.url)
                self.assertEqual(response.status_code, 404)
                self.assertNotContains(response, self.item.name, status_code=404)

    def test_missing_item_returns_404(self):
        url = reverse("wardrobe:item_detail", kwargs={"item_id": self.foreign.pk + 999})
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_read_only_methods(self):
        self.assertEqual(self.client.head(self.url).status_code, 200)
        for method in ("post", "put", "patch", "delete"):
            self.assertEqual(getattr(self.client, method)(self.url).status_code, 405)
        self.assertTrue(WardrobeItem.objects.filter(pk=self.item.pk).exists())

    def test_private_cache_headers_and_json_content_type(self):
        response = self.client.get(self.url)
        self.assertEqual(response["Content-Type"], "application/json")
        self.assertIn("private", response["Cache-Control"])
        self.assertIn("no-store", response["Cache-Control"])
        self.assertIn("Cookie", response["Vary"])

    def test_deleted_category_is_null_and_photos_remain(self):
        self.category.delete()
        data = self.client.get(self.url).json()["item"]
        self.assertIsNone(data["category"])
        self.assertEqual(len(data["photos"]), 3)

    def test_item_without_photos_returns_empty_list(self):
        item = WardrobeItem.objects.create(owner=self.owner, name="Tanpa Foto")
        response = self.client.get(reverse("wardrobe:item_detail", kwargs={"item_id": item.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["item"]["photos"], [])

    def test_response_does_not_expose_storage_paths_or_owner_fields(self):
        storage = WardrobeItemImage._meta.get_field("image").storage
        with patch.object(storage, "open") as open_file:
            response = self.client.get(self.url)
        open_file.assert_not_called()
        self.assertNotIn("owner", response.json()["item"])
        self.assertNotIn("owner_id", response.json()["item"])
        for photo in self.photos.values():
            self.assertNotContains(response, photo.image.name)

    def test_card_triggers_detail_and_only_owned_items_are_listed(self):
        response = self.client.get(reverse("wardrobe:index"))
        self.assertContains(response, f'href="{self.url}" data-item-detail')
        self.assertContains(response, 'aria-controls="item-detail-modal"')
        self.assertContains(response, 'id="item-detail-loading"')
        self.assertContains(response, 'id="retry-item-detail"')
        self.assertNotContains(response, self.foreign.name)
        self.assertNotContains(response, reverse("wardrobe:item_detail", kwargs={"item_id": self.foreign.pk}))

    def test_gallery_photo_urls_still_reject_non_owner(self):
        urls = [p["url"] for p in self.client.get(self.url).json()["item"]["photos"]]
        self.client.force_login(self.other)
        storage = WardrobeItemImage._meta.get_field("image").storage
        with patch.object(storage, "open") as open_file:
            for url in urls:
                self.assertEqual(self.client.get(url).status_code, 404)
        open_file.assert_not_called()
