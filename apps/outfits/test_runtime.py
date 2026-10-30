from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from .api_client import WardrobeAPIError
from .providers import get_stylist_provider


class RealRuntimeTests(TestCase):
    def test_anonymous_landing_has_no_demo_cards(self):
        response = self.client.get(reverse("outfits:index"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["recommendations"], [])
        self.assertNotContains(response, "landing-reference.png")

    @override_settings(OUTFITS_PROVIDER="demo")
    def test_demo_configuration_never_returns_fabricated_matches(self):
        with self.assertRaises(WardrobeAPIError):
            get_stylist_provider()

class ShopMapEmbedTests(TestCase):
    def test_shop_embeds_real_discovery(self):
        response = self.client.get(reverse("marketplace:shop"))
        self.assertContains(response, reverse("marketplace:discovery_map") + "?embed=1")
        self.assertNotContains(response, "map_dummy")

    def test_embedded_map_reuses_endpoints_without_shared_navigation(self):
        response = self.client.get(reverse("marketplace:discovery_map"), {"embed": "1"})
        self.assertContains(response, 'id="discovery-app"')
        self.assertContains(response, reverse("marketplace:api_nearby"))
        self.assertContains(response, "marketplace/js/discovery-map.js")
        self.assertNotContains(response, "navbar-sirkula")
        self.assertNotContains(response, "map-pin-preview")
        self.assertEqual(response.headers["X-Frame-Options"], "SAMEORIGIN")
