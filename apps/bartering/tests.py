from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.marketplace.models import Product

from .models import BarterOffer, BarterTransaction


class BarterFlowTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.seller = user_model.objects.create_user(
            username="seller",
            password="password123",
        )
        self.buyer = user_model.objects.create_user(
            username="buyer",
            password="password123",
        )
        self.requested_product = Product.objects.create(
            seller=self.seller,
            listing_type=Product.ListingType.BARTER,
            name="Jaket",
            price=100000,
        )
        self.offered_product = Product.objects.create(
            seller=self.buyer,
            listing_type=Product.ListingType.BARTER,
            name="Sepatu",
            price=100000,
        )

    def test_user_cannot_create_offer_for_own_product(self):
        self.client.login(username="seller", password="password123")
        response = self.client.get(
            reverse("bartering:offer_create", args=[self.requested_product.pk]),
        )

        self.assertRedirects(response, reverse("marketplace:shop"))
        self.assertFalse(BarterOffer.objects.exists())

    def test_accept_offer_creates_transaction_and_locks_products(self):
        offer = BarterOffer.objects.create(
            proposer=self.buyer,
            recipient=self.seller,
            requested_product=self.requested_product,
            offered_product=self.offered_product,
        )
        self.client.login(username="seller", password="password123")
        response = self.client.post(
            reverse("bartering:update_offer", args=[offer.pk, "ACCEPTED"]),
        )

        self.assertRedirects(response, reverse("bartering:incoming"))
        offer.refresh_from_db()
        self.assertEqual(offer.status, BarterOffer.Status.ACCEPTED)
        self.assertTrue(BarterTransaction.objects.filter(offer=offer).exists())
        self.requested_product.refresh_from_db()
        self.offered_product.refresh_from_db()
        self.assertFalse(self.requested_product.is_available)
        self.assertFalse(self.offered_product.is_available)

    def test_transaction_detail_is_private_to_participants(self):
        other = get_user_model().objects.create_user(
            username="other",
            password="password123",
        )
        offer = BarterOffer.objects.create(
            proposer=self.buyer,
            recipient=self.seller,
            requested_product=self.requested_product,
            offered_product=self.offered_product,
            status=BarterOffer.Status.ACCEPTED,
        )
        transaction = BarterTransaction.objects.create(
            offer=offer,
            proposer=self.buyer,
            recipient=self.seller,
        )
        self.client.login(username="other", password="password123")
        response = self.client.get(
            reverse("bartering:transaction_detail", args=[transaction.pk]),
        )

        self.assertEqual(response.status_code, 404)
