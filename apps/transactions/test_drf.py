from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.marketplace.models import Product
from .models import Order, OrderStatusHistory, TransactionNotification


@override_settings(ROOT_URLCONF='apps.transactions.api_urls_drf')
class TransactionAPITests(TestCase):
    def setUp(self):
        users = get_user_model()
        self.buyer = users.objects.create_user(username='buyer', password='password')
        self.seller = users.objects.create_user(username='seller', password='password')
        self.other = users.objects.create_user(username='other', password='password')
        self.product = Product.objects.create(seller=self.seller, name='Jacket', price=10000, listing_type=Product.ListingType.THRIFT)
        self.client = APIClient()
        self.client.force_authenticate(self.buyer)

    def add_product(self):
        self.assertEqual(self.client.post(f'/cart/items/{self.product.pk}/').status_code, 204)

    def checkout(self):
        return self.client.post('/checkout/', {'address': 'Address', 'phone_number': '123', 'shipping_method': 'REGULAR', 'purchase_method': 'COD'}, format='json')

    @patch('apps.transactions.api_views_drf.create_qris_payment', return_value={'transaction_id': 'payment', 'actions': [{'name': 'generate-qr-code', 'url': 'https://example.com/qr'}]})
    def test_checkout_status_permissions_and_history(self, payment):
        self.add_product()
        response = self.checkout()
        self.assertEqual(response.status_code, 201)
        order_id = response.data['id']
        self.product.refresh_from_db()
        self.assertFalse(self.product.is_available)
        self.assertEqual(Order.objects.get(pk=order_id).total, 13500)
        self.assertEqual(self.client.post(f'/orders/{order_id}/status/', {'status': 'CONFIRMED'}, format='json').status_code, 403)
        self.client.force_authenticate(self.other)
        self.assertEqual(self.client.get(f'/orders/{order_id}/').status_code, 404)
        self.assertEqual(self.client.post(f'/orders/{order_id}/payment-status/').status_code, 404)
        self.client.force_authenticate(self.seller)
        self.assertEqual(self.client.post(f'/orders/{order_id}/status/', {'status': 'COMPLETED'}, format='json').status_code, 400)
        self.assertEqual(self.client.post(f'/orders/{order_id}/status/', {'status': 'CONFIRMED'}, format='json').status_code, 200)
        self.assertEqual(OrderStatusHistory.objects.filter(order_id=order_id).count(), 2)
        self.assertEqual(TransactionNotification.objects.filter(order_id=order_id, recipient=self.buyer).count(), 1)

    @patch('apps.transactions.api_views_drf.create_qris_payment', side_effect=ValueError('failed'))
    def test_payment_creation_failure_restores_product(self, payment):
        self.add_product()
        self.assertEqual(self.checkout().status_code, 502)
        self.product.refresh_from_db()
        self.assertTrue(self.product.is_available)
        self.assertFalse(Order.objects.exists())
        self.assertEqual(len(self.client.get('/cart/').data['items']), 1)
