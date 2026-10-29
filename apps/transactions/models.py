from django.conf import settings
from django.db import models
import uuid

from apps.marketplace.models import Product


def generate_order_number():
    return f"ORD-{uuid.uuid4().hex[:12].upper()}"


class Transaction(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Menunggu konfirmasi"
        CONFIRMED = "CONFIRMED", "Dikonfirmasi"
        SHIPPED = "SHIPPED", "Dikirim"
        COMPLETED = "COMPLETED", "Selesai"
        CANCELLED = "CANCELLED", "Dibatalkan"

    class PurchaseMethod(models.TextChoices):
        COD = "COD", "Cash on Delivery"
        PICKUP = "PICKUP", "Pickup"

    buyer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="purchases",
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        related_name="transactions",
    )
    address = models.CharField(max_length=255)
    phone_number = models.CharField(max_length=30)
    purchase_method = models.CharField(max_length=10, choices=PurchaseMethod.choices)
    shipping_method = models.CharField(max_length=10)
    shipping_cost = models.DecimalField(max_digits=10, decimal_places=0, default=0)
    admin_fee = models.DecimalField(max_digits=10, decimal_places=0, default=0)
    subtotal = models.DecimalField(max_digits=10, decimal_places=0)
    total = models.DecimalField(max_digits=10, decimal_places=0)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Transaksi #{self.pk} - {self.product.name}"


class Order(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Menunggu konfirmasi"
        CONFIRMED = "CONFIRMED", "Dikonfirmasi"
        SHIPPED = "SHIPPED", "Dikirim"
        COMPLETED = "COMPLETED", "Selesai"
        CANCELLED = "CANCELLED", "Dibatalkan"

    class PurchaseMethod(models.TextChoices):
        COD = "COD", "Cash on Delivery"
        PICKUP = "PICKUP", "Pickup"

    buyer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="orders",
    )
    order_number = models.CharField(max_length=32, unique=True, default=generate_order_number)
    address = models.CharField(max_length=255)
    phone_number = models.CharField(max_length=30)
    purchase_method = models.CharField(max_length=10, choices=PurchaseMethod.choices)
    shipping_method = models.CharField(max_length=10)
    shipping_cost = models.DecimalField(max_digits=10, decimal_places=0, default=0)
    admin_fee = models.DecimalField(max_digits=10, decimal_places=0, default=0)
    subtotal = models.DecimalField(max_digits=10, decimal_places=0)
    total = models.DecimalField(max_digits=10, decimal_places=0)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    @property
    def product(self):
        return self.items.select_related("product", "product__seller").first().product

    def __str__(self):
        return f"Order {self.order_number}"


class OrderStatusHistory(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="status_history")
    status = models.CharField(max_length=12, choices=Order.Status.choices)
    note = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]


class TransactionNotification(models.Model):
    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="transaction_notifications")
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="notifications")
    message = models.CharField(max_length=255)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="order_items")
    price = models.DecimalField(max_digits=10, decimal_places=0)

    def __str__(self):
        return f"{self.order} - {self.product.name}"
