import base64
import tempfile
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from rest_framework.test import APITestCase

from apps.transactions.models import Order, OrderItem
from .models import Listing, PredefinedLocation, Product, SavedPlace, Store
from .services import LocationServiceError


@override_settings(ROOT_URLCONF="apps.marketplace.api_urls")
class MarketplaceApiTests(APITestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="seller", password="password")
        self.other = get_user_model().objects.create_user(username="other", password="password")
        self.product = Product.objects.create(seller=self.user, name="Jacket", price=100, location="Jakarta")
        self.hidden = Product.objects.create(seller=self.user, name="Hidden", price=200, is_available=False)

    def test_public_catalog_and_detail(self):
        response = self.client.get("/products/", {"q": "jacket", "min_price": "90"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual([item["id"] for item in response.data], [self.product.pk])
        self.assertEqual(self.client.get(f"/products/{self.hidden.pk}/").status_code, 200)
        self.assertEqual(self.client.get("/products/", {"min_price": "bad"}).status_code, 400)

    def test_owner_is_request_user_and_other_users_cannot_edit(self):
        self.assertIn(self.client.post("/my/products/", {}, format="json").status_code, (401, 403))
        self.client.force_authenticate(self.other)
        response = self.client.post("/my/products/", {"name": "Shirt", "price": "10", "seller": self.user.pk}, format="json")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(Product.objects.get(pk=response.data["id"]).seller, self.other)
        self.assertEqual(self.client.patch(f"/my/products/{self.product.pk}/", {"name": "Stolen"}, format="json").status_code, 404)
        self.assertEqual(self.client.delete(f"/my/products/{self.product.pk}/").status_code, 404)
        self.assertEqual(self.client.get(f"/my/products/{self.product.pk}/images/").status_code, 404)

    def test_product_gallery_upload_and_owner_scoping(self):
        image = base64.b64decode("R0lGODlhAQABAIAAAAAAAP///ywAAAAAAQABAAACAUwAOw==")
        with tempfile.TemporaryDirectory() as media, override_settings(MEDIA_ROOT=media):
            self.client.force_authenticate(self.user)
            response = self.client.post(f"/my/products/{self.product.pk}/images/", {"image": SimpleUploadedFile("a.gif", image, content_type="image/gif"), "order": 2}, format="multipart")
            self.assertEqual(response.status_code, 201)
            image_id = response.data["id"]
            self.assertEqual(len(self.client.get(f"/products/{self.product.pk}/").data["gallery"]), 1)
            self.client.force_authenticate(self.other)
            self.assertEqual(self.client.delete(f"/my/products/{self.product.pk}/images/{image_id}/").status_code, 404)
            self.client.force_authenticate(self.user)
            self.assertEqual(self.client.delete(f"/my/products/{self.product.pk}/images/{image_id}/").status_code, 204)

    def test_delete_product_with_order_preserves_history(self):
        order = Order.objects.create(buyer=self.other, address="A", phone_number="1", purchase_method="delivery", shipping_method="delivery", subtotal=100, total=100)
        OrderItem.objects.create(order=order, product=self.product, price=100)
        self.client.force_authenticate(self.user)
        self.assertEqual(self.client.delete(f"/my/products/{self.product.pk}/").status_code, 204)
        self.product.refresh_from_db()
        self.assertFalse(self.product.is_available)
        self.assertTrue(order.items.exists())

    def test_saved_places_limit_validation_and_ownership(self):
        self.client.force_authenticate(self.user)
        data = {"name": "Place", "address_label": "Jakarta", "latitude": "-6.20", "longitude": "106.80", "user": self.other.pk}
        for _ in range(3):
            self.assertEqual(self.client.post("/map/saved-places/", data, format="json").status_code, 201)
        self.assertEqual(self.client.post("/map/saved-places/", data, format="json").status_code, 400)
        place = SavedPlace.objects.filter(user=self.user).first()
        self.client.force_authenticate(self.other)
        self.assertEqual(self.client.get(f"/map/saved-places/{place.pk}/").status_code, 404)
        data["latitude"] = "91"
        self.assertEqual(self.client.post("/map/saved-places/", data, format="json").status_code, 400)

    def test_nearby_uses_database_distance_and_filters(self):
        PredefinedLocation.objects.create(name="Center", slug="center", address_label="Here", latitude=-6.2, longitude=106.8)
        near = Store.objects.create(name="Near", slug="near", address="Here", latitude=-6.2, longitude=106.8)
        Store.objects.create(name="Far", slug="far", address="Away", latitude=-7, longitude=107)
        Listing.objects.create(store=near, title="Coat", slug="coat", listing_type="thrift", latitude=-6.2, longitude=106.8)
        response = self.client.get("/map/nearby/", {"location": "center", "radius": 3})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["center"]["source"], "predefined")
        self.assertEqual(response.data["counts"], {"stores": 1, "listings": 1})
        self.assertEqual(self.client.get("/map/nearby/", {"lat": 91, "lon": 0}).status_code, 400)
        self.assertEqual(self.client.get("/map/nearby/", {"lat": 0}).status_code, 400)
        self.assertEqual(self.client.get("/map/reverse-geocode/", {"lat": 0, "lon": 181}).status_code, 400)

    @patch("apps.marketplace.api_views.geocode_address", side_effect=LocationServiceError("unavailable"))
    def test_geocoder_errors(self, mocked_geocode):
        self.assertEqual(self.client.get("/map/geocode/", {"q": "ab"}).status_code, 400)
        self.assertEqual(self.client.get("/map/geocode/", {"q": "Jakarta"}).status_code, 503)
        mocked_geocode.assert_called_once_with("Jakarta")
