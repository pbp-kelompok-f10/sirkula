from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.test import Client, TestCase
from django.urls import reverse
from unittest.mock import patch

from .forms import CategoryForm
from .models import Category


class CategoryTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = get_user_model().objects.create_user(username="owner")
        cls.other = get_user_model().objects.create_user(username="other")
        Category.objects.create(owner=cls.other, name="Kategori Rahasia")

    def setUp(self):
        self.client.force_login(self.owner)
        self.url = reverse("create_category")

    def test_wardrobe_shows_only_own_categories(self):
        Category.objects.create(owner=self.owner, name="Kategori Saya")
        response = self.client.get(reverse("wardrobe"))
        self.assertContains(response, "Kategori Saya")
        self.assertNotContains(response, "Kategori Rahasia")
        self.assertContains(response, 'id="category-modal"')

    def test_anonymous_cannot_create_or_see_private_categories(self):
        self.client.logout()
        response = self.client.get(reverse("wardrobe"))
        self.assertNotContains(response, "Kategori Rahasia")
        self.assertNotContains(response, 'id="category-modal"')
        response = self.client.post(self.url, {"name": "Kaos"})
        self.assertEqual(response.status_code, 403)
        self.assertFalse(Category.objects.filter(name="Kaos").exists())

    def test_creation_is_post_only(self):
        self.assertEqual(self.client.get(self.url).status_code, 405)

    def test_owner_is_taken_from_session_and_name_trimmed(self):
        response = self.client.post(self.url, {"name": "  Kaos  ", "owner": self.other.pk})
        self.assertRedirects(response, reverse("wardrobe"))
        self.assertEqual(Category.objects.get(name="Kaos").owner, self.owner)

    def test_different_owners_can_use_same_name(self):
        response = self.client.post(self.url, {"name": "Kategori Rahasia"})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Category.objects.filter(name="Kategori Rahasia").count(), 2)

    def test_duplicate_renders_error_and_reopens_modal(self):
        Category.objects.create(owner=self.owner, name="Kaos")
        response = self.client.post(self.url, {"name": "  kaos  "})
        self.assertContains(response, "Kamu sudah memiliki kategori dengan nama ini.", status_code=400)
        self.assertContains(response, 'aria-invalid="true"', status_code=400)
        self.assertContains(response, 'data-open-on-load="true"', status_code=400)
        self.assertContains(response, 'value="  kaos  "', status_code=400)
        self.assertEqual(Category.objects.filter(owner=self.owner).count(), 1)

    def test_invalid_names(self):
        for name in ("", "   ", "a" * 101):
            with self.subTest(name=name):
                response = self.client.post(self.url, {"name": name})
                self.assertEqual(response.status_code, 400)
                self.assertTrue(response.context["category_form"].errors)
        self.assertFalse(Category.objects.filter(owner=self.owner).exists())

    def test_csrf_required(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.owner)
        self.assertEqual(client.post(self.url, {"name": "Kaos"}).status_code, 403)
        self.assertFalse(Category.objects.filter(owner=self.owner).exists())

    def test_racing_duplicate_is_reported_as_field_error(self):
        Category.objects.create(owner=self.owner, name="Kaos")
        with patch.object(CategoryForm, "clean_name", return_value="Kaos"):
            response = self.client.post(self.url, {"name": "Kaos"})
        self.assertContains(response, "Kamu sudah memiliki kategori dengan nama ini.", status_code=400)

    def test_unexpected_database_error_is_not_masked(self):
        with patch.object(Category, "save", side_effect=IntegrityError("unexpected")):
            with self.assertRaises(IntegrityError):
                self.client.post(self.url, {"name": "Kaos"})

    def test_posted_markup_is_escaped_on_validation_error(self):
        name = '<script>alert("x")</script>'
        Category.objects.create(owner=self.owner, name=name)
        response = self.client.post(self.url, {"name": name})
        self.assertNotContains(response, name, status_code=400)
        self.assertContains(response, "&lt;script&gt;", status_code=400)
