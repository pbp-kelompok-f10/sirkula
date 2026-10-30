from decimal import Decimal

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


LATITUDE_VALIDATORS = [
    MinValueValidator(Decimal("-90")),
    MaxValueValidator(Decimal("90")),
]
LONGITUDE_VALIDATORS = [
    MinValueValidator(Decimal("-180")),
    MaxValueValidator(Decimal("180")),
]


class CoordinateModel(models.Model):
    latitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        validators=LATITUDE_VALIDATORS,
    )
    longitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        validators=LONGITUDE_VALIDATORS,
    )

    class Meta:
        abstract = True


class PredefinedLocation(CoordinateModel):
    class RegionType(models.TextChoices):
        CITY = "city", "Kota"
        REGENCY = "regency", "Kabupaten"

    slug = models.SlugField(max_length=80, unique=True)
    name = models.CharField(max_length=120)
    region_type = models.CharField(max_length=16, choices=RegionType.choices, default=RegionType.CITY)
    address_label = models.CharField(max_length=255)
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ("sort_order", "name")

    def __str__(self):
        return self.name


class Store(CoordinateModel):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="marketplace_stores",
        null=True,
        blank=True,
    )
    name = models.CharField(max_length=150)
    slug = models.SlugField(max_length=170, unique=True)
    description = models.TextField(blank=True)
    address = models.CharField(max_length=255)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("name",)

    def __str__(self):
        return self.name


class Listing(CoordinateModel):
    class ListingType(models.TextChoices):
        THRIFT = "thrift", "Thrift"
        BARTER = "barter", "Barter"

    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name="listings")
    seller = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="marketplace_listings",
        null=True,
        blank=True,
    )
    listing_type = models.CharField(max_length=10, choices=ListingType.choices)
    title = models.CharField(max_length=180)
    slug = models.SlugField(max_length=200, unique=True)
    description = models.TextField(blank=True)
    price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Required for thrift listings, but optional for barter listings.",
    )
    image_url = models.URLField(max_length=500, blank=True)
    is_available = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self):
        return self.title


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
