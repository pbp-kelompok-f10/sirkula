from django.test import SimpleTestCase
from django.urls import resolve, reverse

from .views import home


class HomePageTests(SimpleTestCase):
    def test_root_url_resolves_to_home_view(self):
        match = resolve("/")

        self.assertEqual(match.view_name, "main:home")
        self.assertEqual(match.func, home)

    def test_home_page_renders_successfully(self):
        response = self.client.get(reverse("main:home"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "base.html")
        self.assertTemplateUsed(response, "homepage/home.html")
        self.assertTemplateUsed(response, "homepage/partials/hero.html")
        self.assertTemplateUsed(response, "homepage/partials/features.html")

        self.assertContains(response, "Gaya Tanpa Batas,")
        self.assertContains(response, "Tiga Fitur Keunggulan Kami")