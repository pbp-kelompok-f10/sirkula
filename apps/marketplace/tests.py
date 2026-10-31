import json
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse

from .models import Listing, PredefinedLocation, Product, SavedPlace, Store
from .services import ResolvedCenter, geolocate_ip, haversine_distance_km


class SeedMarketplaceProductsTests(TestCase):
    def test_command_requires_an_existing_account(self):
        with self.assertRaises(CommandError):
            call_command("seed_marketplace_products")

    def test_command_seeds_50_products_without_creating_accounts(self):
        user_model = get_user_model()
        seller = user_model.objects.create_user(username="mockup-seller")

        call_command("seed_marketplace_products", seller=seller.username)

        self.assertEqual(user_model.objects.count(), 1)
        self.assertEqual(Product.objects.filter(seller=seller).count(), 50)
        self.assertEqual(
            Product.objects.filter(seller=seller, listing_type=Product.ListingType.BARTER).count(),
            12,
        )

    def test_command_is_idempotent(self):
        seller = get_user_model().objects.create_user(username="repeat-seller")

        call_command("seed_marketplace_products", seller=seller.username)
        call_command("seed_marketplace_products", seller=seller.username)

        self.assertEqual(Product.objects.filter(seller=seller).count(), 50)

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


class SavedPlaceModelTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(
            username="saved-place-owner",
            password="test-password",
        )

    def test_saved_place_stores_personal_map_pin(self):
        place = SavedPlace.objects.create(
            user=self.user,
            name="Pasar Santa",
            address_label="Jl. Cipaku I, Kebayoran Baru",
            notes="Cari toko pakaian vintage.",
            latitude=Decimal("-6.239889"),
            longitude=Decimal("106.811928"),
        )

        self.assertEqual(str(place), "Pasar Santa")
        self.assertEqual(place.user, self.user)
        self.assertEqual(place.notes, "Cari toko pakaian vintage.")

    def test_saved_place_rejects_invalid_coordinates_on_validation(self):
        place = SavedPlace(
            user=self.user,
            name="Pin tidak valid",
            address_label="Di luar jangkauan koordinat",
            latitude=Decimal("91"),
            longitude=Decimal("181"),
        )

        with self.assertRaises(ValidationError) as error:
            place.full_clean()

        self.assertIn("latitude", error.exception.message_dict)
        self.assertIn("longitude", error.exception.message_dict)

    def test_deleting_user_deletes_their_saved_places(self):
        SavedPlace.objects.create(
            user=self.user,
            name="Pin sementara",
            address_label="Jakarta",
            latitude=Decimal("-6.200000"),
            longitude=Decimal("106.816666"),
        )

        self.user.delete()

        self.assertFalse(SavedPlace.objects.exists())


class SavedPlaceApiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        user_model = get_user_model()
        cls.user = user_model.objects.create_user(username="pin-owner", password="test-password")
        cls.other_user = user_model.objects.create_user(
            username="other-pin-owner",
            password="test-password",
        )
        cls.place = SavedPlace.objects.create(
            user=cls.user,
            name="Pasar Santa",
            address_label="Kebayoran Baru, Jakarta Selatan",
            notes="Cari pakaian vintage.",
            latitude=Decimal("-6.239889"),
            longitude=Decimal("106.811928"),
        )
        cls.other_place = SavedPlace.objects.create(
            user=cls.other_user,
            name="Pin pengguna lain",
            address_label="Jakarta",
            latitude=Decimal("-6.200000"),
            longitude=Decimal("106.816666"),
        )

    def setUp(self):
        self.client.force_login(self.user)

    def test_authentication_is_required(self):
        self.client.logout()

        response = self.client.get(reverse("marketplace:api_saved_places"))

        self.assertEqual(response.status_code, 401)

    def test_list_returns_only_current_users_saved_places(self):
        response = self.client.get(reverse("marketplace:api_saved_places"))

        self.assertEqual(response.status_code, 200)
        result_ids = [item["id"] for item in response.json()["results"]]
        self.assertEqual(result_ids, [self.place.pk])
        self.assertNotIn(self.other_place.pk, result_ids)

    def test_discovery_map_exposes_saved_place_controls_to_authenticated_user(self):
        response = self.client.get(reverse("marketplace:discovery_map"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse("marketplace:api_saved_places"))
        self.assertContains(response, 'id="saved-place-dialog"')
        self.assertContains(response, 'id="saved-place-form"')

    def test_create_assigns_current_user(self):
        response = self.client.post(
            reverse("marketplace:api_saved_places"),
            data=json.dumps(
                {
                    "name": "Blok M Square",
                    "address_label": "Melawai, Jakarta Selatan",
                    "notes": "Cek lantai thrift.",
                    "latitude": -6.2444,
                    "longitude": 106.8007,
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 201)
        place = SavedPlace.objects.get(pk=response.json()["result"]["id"])
        self.assertEqual(place.user, self.user)
        self.assertEqual(place.name, "Blok M Square")

    def test_create_returns_field_errors_for_invalid_coordinates(self):
        response = self.client.post(
            reverse("marketplace:api_saved_places"),
            data=json.dumps(
                {
                    "name": "Pin tidak valid",
                    "address_label": "Tidak diketahui",
                    "notes": "",
                    "latitude": 91,
                    "longitude": 181,
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("latitude", response.json()["error"]["fields"])
        self.assertIn("longitude", response.json()["error"]["fields"])

    def test_detail_hides_another_users_saved_place(self):
        own_response = self.client.get(
            reverse("marketplace:api_saved_place_detail", args=[self.place.pk])
        )
        other_response = self.client.get(
            reverse("marketplace:api_saved_place_detail", args=[self.other_place.pk])
        )

        self.assertEqual(own_response.status_code, 200)
        self.assertEqual(own_response.json()["result"]["name"], self.place.name)
        self.assertEqual(other_response.status_code, 404)

    def test_update_changes_owned_saved_place_without_changing_owner(self):
        response = self.client.put(
            reverse("marketplace:api_saved_place_detail", args=[self.place.pk]),
            data=json.dumps(
                {
                    "name": "Pasar Santa Favorit",
                    "address_label": "Kebayoran Baru, Jakarta Selatan",
                    "notes": "Datang pada akhir pekan.",
                    "latitude": -6.239889,
                    "longitude": 106.811928,
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.place.refresh_from_db()
        self.assertEqual(self.place.name, "Pasar Santa Favorit")
        self.assertEqual(self.place.user, self.user)

    def test_delete_removes_owned_place_but_hides_another_users_place(self):
        other_response = self.client.delete(
            reverse("marketplace:api_saved_place_detail", args=[self.other_place.pk])
        )
        own_response = self.client.delete(
            reverse("marketplace:api_saved_place_detail", args=[self.place.pk])
        )

        self.assertEqual(other_response.status_code, 404)
        self.assertEqual(own_response.status_code, 200)
        self.assertFalse(SavedPlace.objects.filter(pk=self.place.pk).exists())
        self.assertTrue(SavedPlace.objects.filter(pk=self.other_place.pk).exists())


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

    def test_discovery_map_renders_initial_location_and_results(self):
        response = self.client.get(reverse("marketplace:discovery_map"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "marketplace/discovery_map.html")
        self.assertContains(response, "Cari barang di")
        self.assertContains(response, self.location.name)
        self.assertContains(response, self.near_store.name)
        self.assertContains(response, self.listing.title)

    def test_discovery_map_preserves_shared_chrome_and_interaction_hooks(self):
        response = self.client.get(reverse("marketplace:discovery_map"))

        self.assertContains(response, 'class="navbar-brand"')
        self.assertContains(response, 'img/sirkula-mark-figma.svg')
        self.assertContains(response, 'class="footer-site"')
        self.assertContains(response, 'class="footer-mark"')
        self.assertContains(response, reverse("wardrobe:index"))
        self.assertContains(response, reverse("marketplace:shop"))
        self.assertContains(response, 'id="location-search"')
        self.assertContains(response, 'id="radius-slider"')
        self.assertContains(response, 'id="locate-me"')
        self.assertContains(response, 'id="saved-place-list"')
        self.assertContains(response, 'marketplace/js/discovery-map.js')
        self.assertContains(response, 'disabled title="Login diperlukan')
        self.assertNotContains(response, 'id="saved-place-form"')

    def test_authenticated_map_keeps_saved_place_form_and_secure_logout(self):
        user = get_user_model().objects.create_user(
            username="map-chrome-user", password="test-password"
        )
        self.client.force_login(user)
        response = self.client.get(reverse("marketplace:discovery_map"))

        self.assertContains(response, 'id="saved-place-form"')
        self.assertContains(response, 'name="csrfmiddlewaretoken"')
        self.assertContains(
            response, f'method="post" action="{reverse("accounts:logout")}"'
        )
        self.assertContains(response, reverse("accounts:me"))
        self.assertNotContains(response, 'disabled title="Login diperlukan')

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
