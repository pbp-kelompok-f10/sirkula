from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.wardrobe.models import Category, WardrobeItem


class ItemDeleteModalTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = get_user_model().objects.create_user(username="delete-modal-owner")
        cls.other = get_user_model().objects.create_user(username="delete-modal-other")
        cls.category = Category.objects.create(owner=cls.owner, name="Atasan")
        cls.item = WardrobeItem.objects.create(owner=cls.owner, category=cls.category, name="Kaos <Privat>")
        cls.foreign = WardrobeItem.objects.create(owner=cls.other, name="Pakaian Rahasia")

    def test_owned_cards_have_delete_url_and_modal_with_confirmation(self):
        self.client.force_login(self.owner)
        response = self.client.get(reverse("wardrobe:index"), {"category": self.category.pk})
        delete_url = reverse("wardrobe:delete_item", kwargs={"item_id": self.item.pk})
        self.assertContains(response, f'data-item-delete-url="{delete_url}"')
        self.assertContains(response, 'id="open-item-delete"')
        self.assertContains(response, 'id="item-delete-modal"')
        self.assertContains(response, 'id="cancel-item-delete"')
        self.assertContains(response, "Tindakan ini tidak dapat dibatalkan.")
        self.assertContains(response, "Ya, Hapus Permanen")
        self.assertContains(response, "wardrobe/js/item-delete.js", count=1)
        self.assertContains(response, "Kaos &lt;Privat&gt;")
        self.assertEqual(response.context["active_category_id"], self.category.pk)
        self.assertNotContains(response, reverse("wardrobe:delete_item", kwargs={"item_id": self.foreign.pk}))

    def test_anonymous_page_has_no_delete_modal_or_script(self):
        response = self.client.get(reverse("wardrobe:index"))
        self.assertNotContains(response, 'id="item-delete-modal"')
        self.assertNotContains(response, "wardrobe/js/item-delete.js")
