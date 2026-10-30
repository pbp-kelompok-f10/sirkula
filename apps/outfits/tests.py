from copy import deepcopy

from django.contrib.auth import get_user_model
from django.contrib.staticfiles import finders
from django.test import Client, TestCase
from django.urls import reverse

from apps.wardrobe.models import Category, WardrobeItem
from .demo_data import DEMO_HISTORY, DEMO_RECOMMENDATIONS
from .services import get_landing_content


class MixAndMatchLandingTests(TestCase):
    def setUp(self):
        self.url = reverse("outfits:index")

    def test_public_landing_renders_only_requested_sections_with_demo_cards(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "outfits/index.html")
        for text in ("Mix and Match", "Ke Lemari Virtual", "Halo! Bagaimana kamu ingin mix and match pakaianmu?", "Rekomendasi Outfit", "Riwayat"):
            self.assertContains(response, text)
        self.assertContains(response, 'class="mix-card"', count=8)
        self.assertContains(response, 'aria-label="Kirim kebutuhan outfit"')
        self.assertContains(response, 'data-provider="demo"')
        for text in ("Outfit Tersimpan", "Simpan Outfit", "Acak Outfit", "Chat Baru"):
            self.assertNotContains(response, text)
        self.assertFalse(response.context["prompt_form"].is_bound)

    def test_submit_valid_prompt_keeps_landing_and_does_not_save_clothing_or_history(self):
        before = deepcopy(DEMO_HISTORY)
        response = self.client.post(self.url, {"prompt": "  Outfit santai untuk kuliah  ", "category": "7"})
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "outfits/index.html")
        self.assertEqual(response.context["submitted_prompt"], "Outfit santai untuk kuliah")
        self.assertEqual(response.context["wardrobe_url"], reverse("wardrobe:index") + "?category=7")
        self.assertContains(response, "Ini simulasi, bukan hasil AI.")
        self.assertEqual(response.context["history"], list(before))
        self.assertEqual({card["id"] for card in response.context["recommendations"]}, {card["id"] for card in DEMO_RECOMMENDATIONS})
        self.assertFalse(WardrobeItem.objects.exists())
        self.assertEqual(DEMO_HISTORY, before)

    def test_empty_whitespace_and_long_prompts_show_field_errors(self):
        for prompt in ("", "   ", "x" * 501):
            with self.subTest(prompt_length=len(prompt)):
                response = self.client.post(self.url, {"prompt": prompt})
                self.assertEqual(response.status_code, 400)
                self.assertTrue(response.context["prompt_form"].errors.get("prompt"))
                self.assertContains(response, 'aria-invalid="true"', status_code=400)
                self.assertContains(response, 'id="mix-prompt-errors"', status_code=400)

    def test_prompt_is_escaped_in_html(self):
        response = self.client.post(self.url, {"prompt": '\"><script>alert("test")</script>'})
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, '<script>alert("test")</script>')
        self.assertContains(response, "&lt;script&gt;")

    def test_submit_requires_csrf_and_does_not_accept_delete(self):
        secured = Client(enforce_csrf_checks=True)
        self.assertEqual(secured.post(self.url, {"prompt": "Kasual"}).status_code, 403)
        self.assertEqual(self.client.delete(self.url).status_code, 405)
        self.assertEqual(self.client.head(self.url).status_code, 200)

    def test_back_link_keeps_numeric_category_and_rejects_external_return_values(self):
        response = self.client.get(self.url, {"category": "12"})
        self.assertEqual(response.context["wardrobe_url"], reverse("wardrobe:index") + "?category=12")
        for value in ("https://example.org", "-1", "1&next=bad", "0", "9" * 100, "１２"):
            with self.subTest(category=value):
                response = self.client.get(self.url, {"category": value})
                self.assertEqual(response.context["wardrobe_url"], reverse("wardrobe:index"))
                self.assertEqual(response.context["return_category"], "")

    def test_demo_does_not_expose_any_users_real_active_or_draft_clothing(self):
        owner = get_user_model().objects.create_user(username="mix-owner")
        other = get_user_model().objects.create_user(username="mix-other")
        for user in (owner, other):
            WardrobeItem.objects.create(owner=user, name=f"Rahasia aktif {user.username}")
            WardrobeItem.objects.create(owner=user, name=f"Rahasia draft {user.username}", status="draft")
        anonymous = self.client.get(self.url).context["history"]
        self.client.force_login(owner)
        response = self.client.get(self.url)
        self.assertNotContains(response, "Rahasia aktif")
        self.assertNotContains(response, "Rahasia draft")
        self.assertEqual(response.context["history"], anonymous)
        self.assertEqual(WardrobeItem.objects.count(), 4)

    def test_demo_payload_is_fresh_between_requests(self):
        payload = get_landing_content("Kasual")
        payload["recommendations"][0]["title"] = "Tidak boleh bocor"
        payload["history"][0]["image"]["source"] = "changed.png"
        fresh = get_landing_content()
        self.assertNotIn("Tidak boleh bocor", [card["title"] for card in fresh["recommendations"]])
        self.assertNotEqual(fresh["history"][0]["image"]["source"], "changed.png")

    def test_wardrobe_entry_links_keep_current_category(self):
        owner = get_user_model().objects.create_user(username="mix-link-owner")
        category = Category.objects.create(owner=owner, name="Atasan")
        self.client.force_login(owner)
        response = self.client.get(reverse("wardrobe:index"), {"category": category.pk})
        url = self.url + f"?category={category.pk}"
        self.assertContains(response, f'href="{url}"')
        self.assertContains(response, f'href="{url}#mix-prompt"')
        self.assertContains(response, "Mix and Match Outfit")

    def test_demo_assets_are_available_from_registered_app(self):
        self.assertIsNotNone(finders.find("outfits/css/landing.css"))
        self.assertIsNotNone(finders.find("outfits/img/landing-reference.png"))
