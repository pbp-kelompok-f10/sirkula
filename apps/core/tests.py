from django.test import SimpleTestCase, override_settings
from django.template.loader import render_to_string
from django.urls import include, path, resolve, reverse

from apps.core.views import home


# Isolate homepage tests from unfinished URL configurations in other apps.
urlpatterns = [path("", include("apps.core.urls"))]


@override_settings(ROOT_URLCONF="apps.core.tests")
class HomePageTests(SimpleTestCase):
    def test_root_url_resolves_to_home_view(self):
        match = resolve("/")
        self.assertEqual(match.view_name, "core:home")
        self.assertEqual(match.func, home)

    def test_home_page_renders_successfully(self):
        response = self.client.get(reverse("core:home"))
        self.assertEqual(response.status_code, 200)
        for template in (
            "base.html",
            "core/home.html",
            "core/partials/hero.html",
            "core/partials/features.html",
            "core/partials/how_it_works.html",
            "layouts/site.html",
            "components/header.html",
            "components/navbar.html",
            "components/footer.html",
        ):
            self.assertTemplateUsed(response, template)
        self.assertContains(response, "Gaya Tanpa Batas,")
        self.assertContains(response, "What’s Different From Us?")

    def test_homepage_uses_tailwind_without_legacy_reset(self):
        response = self.client.get(reverse("core:home"))
        self.assertContains(response, 'css/app.css')
        self.assertNotContains(response, 'css/style.css')

    def test_default_base_preserves_team_stylesheet(self):
        html = render_to_string("index.html")
        self.assertIn("css/style.css", html)
        self.assertNotIn("css/app.css", html)

    def test_final_sections_and_unique_landmarks(self):
        response = self.client.get(reverse("core:home"))
        for text in ("Pindai lemarimu", "Temukan barang impianmu", "Tukar tanpa uang tunai", "Bantu Kami"):
            self.assertContains(response, text)
        html = response.content.decode()
        self.assertEqual(html.count("<h1"), 1)
        self.assertEqual(html.count("<header"), 1)
        self.assertEqual(html.count("<footer"), 1)

    def test_navigation_links_and_home_active_state(self):
        from html.parser import HTMLParser

        class Links(HTMLParser):
            def __init__(self):
                super().__init__()
                self.items = []
                self.current = None

            def handle_starttag(self, tag, attrs):
                if tag == "a":
                    self.current = [dict(attrs), ""]

            def handle_data(self, data):
                if self.current is not None:
                    self.current[1] += data

            def handle_endtag(self, tag):
                if tag == "a" and self.current is not None:
                    self.items.append(self.current)
                    self.current = None

        response = self.client.get(reverse("core:home"))
        parser = Links()
        parser.feed(response.content.decode())
        links = {text.strip(): attrs for attrs, text in parser.items}
        for label, target in {
            "Home": "/",
            "Wardrobe": "/wardrobe/",
            "Barter": "/barter/",
            "Thrift": "/marketplace/",
            "Register": "/accounts/register/",
            "Login": "/accounts/login/",
            "Jelajahi Lemari Virtual": "/wardrobe/",
            "Mulai Barter/Thrift": "/barter/",
        }.items():
            self.assertEqual(links[label]["href"], target)
        active = [text.strip() for attrs, text in parser.items if attrs.get("aria-current") == "page"]
        self.assertEqual(active, ["Home"])

    def test_shared_layout_can_render_another_apps_page(self):
        from types import SimpleNamespace

        from django.template import engines
        from django.test import RequestFactory

        request = RequestFactory().get("/wardrobe/")
        request.resolver_match = SimpleNamespace(
            namespace="wardrobe", view_name="wardrobe:index"
        )
        template = engines["django"].from_string(
            '{% extends "layouts/site.html" %}'
            '{% block title %}Wardrobe | Sirkula{% endblock %}'
            '{% block page_content %}<h1>Wardrobe test page</h1>{% endblock %}'
        )
        html = template.render({}, request=request)
        self.assertIn("<title>Wardrobe | Sirkula</title>", html)
        self.assertIn("Wardrobe test page", html)
        self.assertIn("css/app.css", html)
        self.assertNotIn("css/style.css", html)
        self.assertNotIn("Gaya Tanpa Batas", html)
        self.assertEqual(html.count("<main"), 1)
        self.assertEqual(html.count("<header"), 1)
        self.assertEqual(html.count("<footer"), 1)
        self.assertRegex(html, r'href="/wardrobe/"\s+aria-current="page"')
