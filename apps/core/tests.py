from collections import Counter
from html.parser import HTMLParser

from django.test import TestCase, override_settings
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
class HomePageTests(TestCase):
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


class ReviewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        from django.contrib.auth import get_user_model
        from .models import Review

        users = get_user_model()
        cls.owner = users.objects.create_user(username="review-owner", password="test-pass")
        cls.reader = users.objects.create_user(username="review-reader", password="test-pass")
        cls.moderator = users.objects.create_superuser(username="review-mod", password="test-pass", email="mod@example.test")
        cls.review = Review.objects.create(author=cls.owner, content="Sirkula membantu saya menemukan gaya baru.")

    def test_public_can_read_but_cannot_see_owner_controls(self):
        response = self.client.get(reverse("core:home"))
        self.assertContains(response, self.review.content)
        self.assertContains(response, 'overflow-x-auto')
        self.assertNotContains(response, reverse("core:review_update", args=[self.review.pk]))
        self.assertNotContains(response, reverse("core:review_delete", args=[self.review.pk]))

    def test_anonymous_mutations_require_login(self):
        from .models import Review, ReviewLike
        urls = [reverse("core:review_create")] + [
            reverse(name, args=[self.review.pk])
            for name in ("core:review_update", "core:review_delete", "core:review_like")
        ]
        for url in urls:
            response = self.client.post(url, {"content": "Unauthorized review update", "action": "like"})
            self.assertEqual(response.status_code, 302)
            self.assertTrue(response.url.startswith("/accounts/login/?next="))
        self.assertEqual(Review.objects.count(), 1)
        self.assertEqual(ReviewLike.objects.count(), 0)
        self.review.refresh_from_db()
        self.assertEqual(self.review.content, "Sirkula membantu saya menemukan gaya baru.")

    def test_create_uses_authenticated_author_and_redirects(self):
        from .models import Review
        self.client.force_login(self.reader)
        response = self.client.post(reverse("core:review_create"), {
            "content": "Website ini mudah digunakan dan sangat membantu.",
            "author": self.owner.pk,
        })
        self.assertRedirects(response, reverse("core:home") + "#reviews")
        self.assertTrue(Review.objects.filter(author=self.reader).exists())

    def test_form_rejects_empty_short_and_long_content(self):
        from .models import Review
        self.client.force_login(self.reader)
        for content in ("", "    ", "pendek", "a" * 1001):
            response = self.client.post(reverse("core:review_create"), {"content": content})
            self.assertEqual(response.status_code, 200)
            self.assertIn("content", response.context["form"].errors)
        self.assertFalse(Review.objects.filter(author=self.reader).exists())

    def test_duplicate_review_redirects_to_edit(self):
        from .models import Review
        self.client.force_login(self.owner)
        response = self.client.post(reverse("core:review_create"), {"content": "Another review from same user"})
        self.assertRedirects(response, reverse("core:review_update", args=[self.review.pk]))
        self.assertEqual(Review.objects.filter(author=self.owner).count(), 1)

    def test_owner_can_edit_without_changing_author(self):
        self.client.force_login(self.owner)
        response = self.client.post(reverse("core:review_update", args=[self.review.pk]), {
            "content": "Ulasan saya sudah diperbarui dengan pengalaman terbaru.", "author": self.reader.pk,
        })
        self.assertEqual(response.status_code, 302)
        self.review.refresh_from_db()
        self.assertEqual(self.review.author_id, self.owner.pk)
        self.assertIn("diperbarui", self.review.content)

    def test_other_users_and_superuser_cannot_edit(self):
        url = reverse("core:review_update", args=[self.review.pk])
        for user in (self.reader, self.moderator):
            self.client.force_login(user)
            self.assertEqual(self.client.get(url).status_code, 403)
            self.assertEqual(self.client.post(url, {"content": "Unauthorized change"}).status_code, 403)
        self.review.refresh_from_db()
        self.assertNotEqual(self.review.content, "Unauthorized change")

    def test_other_user_cannot_delete(self):
        from .models import Review
        self.client.force_login(self.reader)
        url = reverse("core:review_delete", args=[self.review.pk])
        self.assertEqual(self.client.get(url).status_code, 403)
        self.assertEqual(self.client.post(url).status_code, 403)
        self.assertTrue(Review.objects.filter(pk=self.review.pk).exists())

    def test_delete_requires_confirmation_post_and_removes_likes(self):
        from .models import Review, ReviewLike
        ReviewLike.objects.create(review=self.review, user=self.reader)
        self.client.force_login(self.owner)
        url = reverse("core:review_delete", args=[self.review.pk])
        self.assertEqual(self.client.get(url).status_code, 200)
        self.assertTrue(Review.objects.filter(pk=self.review.pk).exists())
        self.assertEqual(self.client.post(url).status_code, 302)
        self.assertFalse(Review.objects.filter(pk=self.review.pk).exists())
        self.assertEqual(ReviewLike.objects.count(), 0)

    def test_superuser_can_moderate_but_staff_alone_cannot(self):
        from .models import Review
        self.reader.is_staff = True
        self.reader.save(update_fields=["is_staff"])
        url = reverse("core:review_delete", args=[self.review.pk])
        self.client.force_login(self.reader)
        self.assertEqual(self.client.post(url).status_code, 403)
        self.client.force_login(self.moderator)
        self.assertEqual(self.client.post(url).status_code, 302)
        self.assertFalse(Review.objects.filter(pk=self.review.pk).exists())

    def test_like_and_unlike_are_idempotent(self):
        from .models import ReviewLike
        self.client.force_login(self.reader)
        url = reverse("core:review_like", args=[self.review.pk])
        for _ in range(2):
            self.assertEqual(self.client.post(url, {"action": "like"}).status_code, 302)
        self.assertEqual(ReviewLike.objects.count(), 1)
        response = self.client.get(reverse("core:home"))
        self.assertContains(response, 'aria-pressed="true"')
        self.assertEqual(response.context["reviews_page"].object_list[0].like_count, 1)
        for _ in range(2):
            self.assertEqual(self.client.post(url, {"action": "unlike"}).status_code, 302)
        self.assertEqual(ReviewLike.objects.count(), 0)

    def test_like_rejects_get_invalid_action_and_self_like(self):
        from .models import ReviewLike
        url = reverse("core:review_like", args=[self.review.pk])
        self.client.force_login(self.reader)
        self.assertEqual(self.client.get(url).status_code, 405)
        self.assertEqual(self.client.post(url, {"action": "invalid"}).status_code, 400)
        self.client.force_login(self.owner)
        self.assertEqual(self.client.post(url, {"action": "like"}).status_code, 403)
        self.assertEqual(ReviewLike.objects.count(), 0)

    def test_mutations_enforce_csrf(self):
        from django.test import Client
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.owner)
        for name in ("core:review_update", "core:review_delete", "core:review_like"):
            self.assertEqual(client.post(reverse(name, args=[self.review.pk]), {"content": "Some updated review", "action": "like"}).status_code, 403)
        self.assertEqual(client.post(reverse("core:review_create"), {"content": "Another review"}).status_code, 403)

    def test_review_content_is_escaped(self):
        self.review.content = '<script>alert("xss")</script>'
        self.review.save()
        response = self.client.get(reverse("core:home"))
        self.assertContains(response, "&lt;script&gt;")
        self.assertNotContains(response, '<script>alert("xss")</script>')

    def test_missing_review_returns_404(self):
        self.client.force_login(self.reader)
        for name in ("core:review_update", "core:review_delete", "core:review_like"):
            self.assertEqual(self.client.post(reverse(name, args=[99999]), {"action": "like"}).status_code, 404)

    def test_paginated_reviews_remain_public_and_queries_are_bounded(self):
        from django.contrib.auth import get_user_model
        from .models import Review
        for i in range(21):
            user = get_user_model().objects.create_user(username=f"review-extra-{i}")
            Review.objects.create(author=user, content=f"Pengalaman pengguna nomor {i} di Sirkula.")
        with self.assertNumQueries(2):
            response = self.client.get(reverse("core:home"))
        self.assertEqual(len(response.context["reviews_page"]), 20)
        response = self.client.get(reverse("core:home"), {"reviews_page": 2})
        self.assertEqual(len(response.context["reviews_page"]), 2)
        self.assertContains(response, self.review.content)
        self.assertEqual(self.client.get(reverse("core:home"), {"reviews_page": "invalid"}).status_code, 200)


    def test_superuser_can_publish_multiple_reviews(self):
        from .models import Review
        self.client.force_login(self.moderator)
        for i in range(3):
            response = self.client.post(reverse("core:review_create"), {"content": f"Cerita superuser nomor {i} untuk komunitas."})
            self.assertEqual(response.status_code, 302)
        self.assertEqual(Review.objects.filter(author=self.moderator).count(), 3)
        self.assertEqual(Review.objects.filter(author=self.moderator, is_superuser_submission=True).count(), 3)
        response = self.client.get(reverse("core:home"))
        self.assertContains(response, "Tambah ulasan")
        self.assertContains(response, "Cerita Mereka, Inspirasi Kita")

    def test_regular_user_cannot_claim_superuser_submission(self):
        from .models import Review
        self.client.force_login(self.reader)
        self.client.post(reverse("core:review_create"), {"content": "Ulasan pengguna biasa yang valid.", "is_superuser_submission": "True"})
        review = Review.objects.get(author=self.reader)
        self.assertFalse(review.is_superuser_submission)
        self.client.post(reverse("core:review_create"), {"content": "Ulasan kedua yang harus ditolak."})
        self.assertEqual(Review.objects.filter(author=self.reader).count(), 1)

    def test_database_enforces_regular_review_limit(self):
        from django.db import IntegrityError, transaction
        from .models import Review
        with self.assertRaises(IntegrityError), transaction.atomic():
            Review.objects.create(author=self.owner, content="Ulasan kedua dari akun biasa.")
