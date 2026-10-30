from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.marketplace.models import Product

from .models import Order, OrderItem


class TransactionFlowTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.buyer = user_model.objects.create_user(
            username="buyer",
            password="password123",
        )
        self.seller = user_model.objects.create_user(
            username="seller",
            password="password123",
        )
        self.other_user = user_model.objects.create_user(
            username="other",
            password="password123",
        )
        self.product = Product.objects.create(
            seller=self.seller,
            listing_type=Product.ListingType.THRIFT,
            name="Jaket Test",
            price=Decimal("50000"),
        )

    def create_order(self):
        order = Order.objects.create(
            buyer=self.buyer,
            address="Jl. Test",
            phone_number="08123456789",
            purchase_method=Order.PurchaseMethod.COD,
            shipping_method="REGULAR",
            shipping_cost=Decimal("2500"),
            admin_fee=Decimal("1000"),
            subtotal=Decimal("50000"),
            total=Decimal("53500"),
        )
        OrderItem.objects.create(
            order=order,
            product=self.product,
            price=self.product.price,
        )
        return order

    def test_buyer_can_view_purchase_list(self):
        self.create_order()
        self.client.force_login(self.buyer)

        response = self.client.get(reverse("transactions:purchases"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Jaket Test")

    def test_seller_can_view_sales_list(self):
        self.create_order()
        self.client.force_login(self.seller)

        response = self.client.get(reverse("transactions:sales"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Jaket Test")

    def test_unrelated_user_cannot_view_order_detail(self):
        order = self.create_order()
        self.client.force_login(self.other_user)

        response = self.client.get(
            reverse("transactions:detail", args=[order.pk]),
        )

        self.assertRedirects(response, reverse("transactions:purchases"))

    def test_only_seller_can_update_order_status(self):
        order = self.create_order()
        self.client.force_login(self.buyer)

        response = self.client.post(
            reverse("transactions:update_status", args=[order.pk]),
            {"status": Order.Status.CONFIRMED},
        )

        order.refresh_from_db()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(order.status, Order.Status.PENDING)

    def test_seller_can_confirm_order(self):
        order = self.create_order()
        self.client.force_login(self.seller)

        response = self.client.post(
            reverse("transactions:update_status", args=[order.pk]),
            {"status": Order.Status.CONFIRMED},
        )

        order.refresh_from_db()
        self.assertRedirects(
            response,
            reverse("transactions:detail", args=[order.pk]),
        )
        self.assertEqual(order.status, Order.Status.CONFIRMED)

    def test_order_stores_shipping_and_admin_fee_once(self):
        order = self.create_order()
        OrderItem.objects.create(
            order=order,
            product=Product.objects.create(
                seller=self.seller,
                listing_type=Product.ListingType.THRIFT,
                name="Celana Test",
                price=Decimal("25000"),
            ),
            price=Decimal("25000"),
        )

        self.assertEqual(order.admin_fee, Decimal("1000"))
        self.assertEqual(order.shipping_cost, Decimal("2500"))
        self.assertEqual(order.items.count(), 2)
