from django.conf import settings
from django.db import models

from apps.marketplace.models import Product


class BarterOffer(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Menunggu keputusan"
        ACCEPTED = "ACCEPTED", "Diterima"
        SHIPPING = "SHIPPING", "Dalam pengiriman"
        COMPLETED = "COMPLETED", "Selesai"
        REJECTED = "REJECTED", "Ditolak"
        CANCELLED = "CANCELLED", "Dibatalkan"

    proposer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="barter_offers_sent",
    )
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="barter_offers_received",
    )
    requested_product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        related_name="barter_offers_received",
    )
    offered_product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        related_name="barter_offers_sent",
    )
    message = models.TextField(blank=True)
    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.PENDING,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    proposer_tracking_number = models.CharField(max_length=100, blank=True)
    recipient_tracking_number = models.CharField(max_length=100, blank=True)
    proposer_received = models.BooleanField(default=False)
    recipient_received = models.BooleanField(default=False)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["proposer", "requested_product", "offered_product"],
                condition=models.Q(status="PENDING"),
                name="one_pending_offer_per_product_pair",
            ),
        ]

    def __str__(self):
        return f"Barter #{self.pk}: {self.offered_product} → {self.requested_product}"


class BarterTransaction(models.Model):
    offer = models.OneToOneField(
        BarterOffer,
        on_delete=models.PROTECT,
        related_name="transaction",
    )
    proposer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="barter_transactions_as_proposer",
    )
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="barter_transactions_as_recipient",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        return f"Transaksi barter #{self.pk}"
