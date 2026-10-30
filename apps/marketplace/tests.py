from decimal import Decimal
from unittest.mock import patch

from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse

from .models import Listing, PredefinedLocation, Store
from .services import ResolvedCenter, geolocate_ip, haversine_distance_km

# === Geolocation test (buat discovery map) === #
class DistanceServiceTests(TestCase):
    def test_haversine_distance_is_zero_for_same_point(self):
        distance = haversine_distance_km(-6.186486, 106.834091, -6.186486, 106.834091)
        self.assertEqual(distance, 0)

    def test_haversine_distance_uses_kilometres(self):
        distance = haversine_distance_km(-6.186486, 106.834091, -6.195, 106.834091)
        self.assertAlmostEqual(distance, 0.95, places=1)


@override_settings(MARKETPLACE_DEFAULT_CENTER=(-6.186486, 106.834091))
class IpGeolocationTests(TestCase):
    def test_private_ip_uses_safe_default_without_external_request(self):
        with patch("apps.marketplace.services._request_json") as request_json:
            result = geolocate_ip("127.0.0.1")

        request_json.assert_not_called()
        self.assertEqual(result.source, "fallback")
        self.assertEqual(result.label, "Jakarta Pusat")

    @patch("apps.marketplace.services._request_json")
    def test_public_ip_uses_configured_provider(self, request_json):
        request_json.return_value = {
            "latitude": -6.2,
            "longitude": 106.8,
            "city": "Jakarta",
        }
        result = geolocate_ip("8.8.8.8")

        self.assertEqual(result, ResolvedCenter(-6.2, 106.8, "Jakarta", "ip"))
# === Geolocation test (buat discovery map) === #

# Marketplace test (nanti diubah abis pr)
class MarketplaceApiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.location = PredefinedLocation.objects.create(
            slug="test-jakarta-pusat",
            name="Jakarta Pusat Test",
            region_type=PredefinedLocation.RegionType.CITY,
            address_label="Menteng, Jakarta Pusat",
            latitude=Decimal("-6.186486"),
            longitude=Decimal("106.834091"),
            sort_order=1,
        )
        cls.near_store = Store.objects.create(
            name="Near Store",
            slug="test-near-store",
            description="Nearby thrift store",
            address="Menteng",
            latitude=Decimal("-6.187000"),
            longitude=Decimal("106.834091"),
        )
        cls.far_store = Store.objects.create(
            name="Far Store",
            slug="test-far-store",
            description="Outside the selected radius",
            address="Bogor",
            latitude=Decimal("-6.595038"),
            longitude=Decimal("106.816635"),
        )
        cls.listing = Listing.objects.create(
            store=cls.near_store,
            listing_type=Listing.ListingType.THRIFT,
            title="Test Jacket",
            slug="test-jacket-api",
            description="A nearby denim jacket",
            price=Decimal("100000.00"),
            latitude=cls.near_store.latitude,
            longitude=cls.near_store.longitude,
        )

    def test_predefined_locations_support_search(self):
        response = self.client.get(reverse("marketplace:api_locations"), {"q": "Menteng"})

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(any(item["slug"] == self.location.slug for item in payload["results"]))

    def test_nearby_accepts_exact_coordinates_and_sorts_by_distance(self):
        response = self.client.get(
            reverse("marketplace:api_nearby"),
            {"lat": -6.186486, "lon": 106.834091, "radius": 3},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["center"]["source"], "coordinates")
        self.assertEqual(payload["stores"][0]["slug"], self.near_store.slug)
        self.assertNotIn(self.far_store.slug, [item["slug"] for item in payload["stores"]])
        self.assertEqual(payload["listings"][0]["slug"], self.listing.slug)

    def test_nearby_accepts_predefined_location(self):
        response = self.client.get(
            reverse("marketplace:api_nearby"),
            {"location": self.location.slug, "radius": 3},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["center"]["source"], "predefined")

    @patch("apps.marketplace.views.geolocate_ip")
    def test_nearby_uses_ip_resolution_when_location_is_omitted(self, geolocate):
        geolocate.return_value = ResolvedCenter(-6.186486, 106.834091, "Jakarta", "ip")
        response = self.client.get(reverse("marketplace:api_nearby"), {"radius": 3})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["center"]["source"], "ip")
        geolocate.assert_called_once()

    def test_nearby_rejects_incomplete_coordinates(self):
        response = self.client.get(reverse("marketplace:api_nearby"), {"lat": -6.18})

        self.assertEqual(response.status_code, 400)
        self.assertIn("together", response.json()["error"]["message"])

    def test_nearby_rejects_out_of_range_radius(self):
        response = self.client.get(
            reverse("marketplace:api_nearby"),
            {"lat": -6.18, "lon": 106.83, "radius": 1000},
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"]["field"], "radius")

    def test_nearby_search_filters_stores_and_listings(self):
        response = self.client.get(
            reverse("marketplace:api_nearby"),
            {"lat": -6.186486, "lon": 106.834091, "radius": 3, "q": "Jacket"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["counts"]["listings"], 1)
        self.assertEqual(response.json()["counts"]["stores"], 0)

    @patch("apps.marketplace.views.geocode_address")
    def test_geocode_proxies_provider_results(self, geocode_address):
        geocode_address.return_value = [
            {"latitude": -6.2, "longitude": 106.8, "label": "Jakarta"}
        ]
        response = self.client.get(reverse("marketplace:api_geocode"), {"q": "Jakarta"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["results"][0]["label"], "Jakarta")

    def test_geocode_requires_meaningful_query(self):
        response = self.client.get(reverse("marketplace:api_geocode"), {"q": "ab"})

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"]["field"], "q")

    @patch("apps.marketplace.views.reverse_geocode")
    def test_reverse_geocode_validates_and_proxies_coordinates(self, reverse_geocode):
        reverse_geocode.return_value = {
            "latitude": -6.2,
            "longitude": 106.8,
            "label": "Jakarta",
            "address": {},
        }
        response = self.client.get(
            reverse("marketplace:api_reverse_geocode"),
            {"lat": -6.2, "lon": 106.8},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["result"]["label"], "Jakarta")
