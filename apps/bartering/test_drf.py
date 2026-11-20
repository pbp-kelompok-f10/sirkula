from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.marketplace.models import Product
from .models import BarterOffer, BarterTransaction


@override_settings(ROOT_URLCONF='apps.bartering.api_urls_drf')
class BarterAPITests(TestCase):
    def setUp(self):
        users = get_user_model()
        self.proposer = users.objects.create_user(username='proposer', password='password')
        self.recipient = users.objects.create_user(username='recipient', password='password')
        self.other = users.objects.create_user(username='other', password='password')
        self.requested = Product.objects.create(seller=self.recipient, name='Requested', price=100, listing_type=Product.ListingType.BARTER)
        self.offered = Product.objects.create(seller=self.proposer, name='Offered', price=100, listing_type=Product.ListingType.BARTER)
        self.client = APIClient()
        self.client.force_authenticate(self.proposer)

    def create_offer(self):
        return self.client.post('/offers/', {'requested_product': self.requested.pk, 'offered_product': self.offered.pk}, format='json')

    def test_offer_ownership_conflicts_and_privacy(self):
        response = self.create_offer()
        self.assertEqual(response.status_code, 201)
        self.assertEqual(self.create_offer().status_code, 400)
        self.client.force_authenticate(self.other)
        self.assertEqual(self.client.get(f"/offers/{response.data['id']}/").status_code, 404)
        self.assertEqual(self.client.post(f"/offers/{response.data['id']}/accept/").status_code, 404)
        self.assertEqual(self.create_offer().status_code, 400)

    def test_accept_shipping_and_receipt(self):
        response = self.create_offer()
        offer_id = response.data['id']
        self.assertEqual(self.client.post(f'/offers/{offer_id}/accept/').status_code, 403)
        self.client.force_authenticate(self.recipient)
        self.assertEqual(self.client.post(f'/offers/{offer_id}/accept/').status_code, 200)
        self.requested.refresh_from_db()
        self.offered.refresh_from_db()
        self.assertFalse(self.requested.is_available)
        self.assertFalse(self.offered.is_available)
        self.assertTrue(BarterTransaction.objects.filter(offer_id=offer_id).exists())
        self.assertEqual(self.client.post(f'/offers/{offer_id}/received/').status_code, 400)
        self.client.post(f'/offers/{offer_id}/shipping/', {'tracking_number': 'R1'}, format='json')
        self.client.force_authenticate(self.proposer)
        self.client.post(f'/offers/{offer_id}/shipping/', {'tracking_number': 'R2'}, format='json')
        self.client.post(f'/offers/{offer_id}/received/')
        self.client.force_authenticate(self.recipient)
        self.client.post(f'/offers/{offer_id}/received/')
        offer = BarterOffer.objects.get(pk=offer_id)
        self.assertEqual(offer.status, BarterOffer.Status.COMPLETED)
        self.assertIsNotNone(offer.transaction.completed_at)
