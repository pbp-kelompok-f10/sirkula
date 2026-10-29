from collections import Counter
from html.parser import HTMLParser

from django.test import SimpleTestCase, override_settings
from django.template.loader import render_to_string
from django.urls import include, path, resolve, reverse

from apps.core.views import home


class PageMarkup(HTMLParser):
    """Inspect actual elements without counting HTML inside comments."""

    def __init__(self):
        super().__init__()
        self.tags = Counter()
        self.ids = Counter()
        self.stylesheets = []

    def handle_starttag(self, tag, attrs):
        self.tags[tag] += 1
        attrs = dict(attrs)
        if "id" in attrs:
            self.ids[attrs["id"]] += 1
        if tag == "link" and attrs.get("rel") == "stylesheet":
            self.stylesheets.append(attrs.get("href", ""))


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
        ):
            self.assertTemplateUsed(response, template)
        self.assertContains(response, "Gaya Tanpa Batas,")
        self.assertContains(response, "What’s Different From Us?")

    def test_homepage_uses_tailwind_without_legacy_reset(self):
        response = self.client.get(reverse("core:home"))
        self.assertContains(response, 'css/dist/styles.css')
        self.assertNotContains(response, 'css/app.css')
        self.assertNotContains(response, 'css/style.css')

    def test_default_base_uses_design_system_stylesheet(self):
        html = render_to_string("index.html")
        self.assertIn("css/dist/styles.css", html)
        self.assertNotIn("css/style.css", html)
        self.assertNotIn("css/app.css", html)

    def test_final_sections_and_unique_landmarks(self):
        response = self.client.get(reverse("core:home"))
        for text in ("Pindai lemarimu", "Temukan barang impianmu", "Tukar tanpa uang tunai", "Bantu Kami"):
            self.assertContains(response, text)
        html = response.content.decode()
        self.assert_unique_landmarks(html)
        markup = PageMarkup()
        markup.feed(html)
        self.assertEqual(markup.tags["h1"], 1)

    def test_home_link_cta_destinations_and_active_state(self):
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
            namespace="wardrobe", view_name="wardrobe:index", url_name="index"
        )
        template = engines["django"].from_string(
            '{% extends "layouts/site.html" %}'
            '{% block title %}Wardrobe | Sirkula{% endblock %}'
            '{% block page_content %}<h1>Wardrobe test page</h1>{% endblock %}'
        )
        html = template.render({}, request=request)
        self.assertIn("<title>Wardrobe | Sirkula</title>", html)
        self.assertIn("Wardrobe test page", html)
        self.assertIn("css/dist/styles.css", html)
        self.assertNotIn("css/app.css", html)
        self.assertNotIn("css/style.css", html)
        self.assertNotIn("Gaya Tanpa Batas", html)
        self.assert_unique_landmarks(html)

    def assert_unique_landmarks(self, html):
        markup = PageMarkup()
        markup.feed(html)
        for tag in ("main", "header", "footer"):
            self.assertEqual(markup.tags[tag], 1, tag)
        self.assertEqual(markup.ids["main-content"], 1)
        self.assertEqual(
            [href for href in markup.stylesheets if href.startswith("/static/")],
            ["/static/css/dist/styles.css"],
        )

    def test_component_catalog_remains_available(self):
        response = self.client.get(reverse("core:show_components"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "components.html")
        self.assertContains(response, "css/dist/styles.css")

    def test_home_template_and_image_belong_to_core_app(self):
        from pathlib import Path
        from django.contrib.staticfiles import finders
        from django.template.loader import get_template

        core_dir = Path(__file__).resolve().parent
        self.assertEqual(
            Path(get_template("core/home.html").origin.name).resolve(),
            core_dir / "templates/core/home.html",
        )
        image = finders.find("core/img/hero-final.jpg")
        self.assertIsNotNone(image)
        self.assertEqual(Path(image).resolve(), core_dir / "static/core/img/hero-final.jpg")
        response = self.client.get(reverse("core:home"))
        self.assertContains(response, "/static/core/img/hero-final.jpg")
        self.assertTemplateUsed(response, "core/components/feature_card.html")
