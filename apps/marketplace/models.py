from django.conf import settings
from django.db import models


class Product(models.Model):
    class ListingType(models.TextChoices):
        THRIFT = "THRIFT", "Thrift"
        BARTER = "BARTER", "Barter"

    seller = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="products",
    )
    listing_type = models.CharField(
        max_length=10,
        choices=ListingType.choices,
        default=ListingType.THRIFT,
    )
    name = models.CharField(max_length=255)
    brand = models.CharField(max_length=100, blank=True)
    size = models.CharField(max_length=50, blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=0)
    image = models.ImageField(upload_to="products/", blank=True, null=True)
    description = models.TextField(blank=True)
    usage_duration = models.CharField(max_length=100, blank=True)
    barter_reason = models.TextField(blank=True)
    barter_wanted = models.TextField(
        blank=True,
        help_text="Satu barang per baris.",
    )
    location = models.CharField(max_length=255, blank=True)
    is_available = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} - {self.seller}"

    @property
    def barter_wanted_list(self):
        return [
            line.strip()
            for line in self.barter_wanted.splitlines()
            if line.strip()
        ]


class ProductImage(models.Model):
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="gallery",
    )
    image = models.ImageField(upload_to="products/gallery/")
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return f"Foto {self.order} - {self.product.name}"
