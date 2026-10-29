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
    # Sistem koordinat buat ditaruh di database

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
    region_type = models.CharField(
        max_length=16,
        choices=RegionType.choices,
        default=RegionType.CITY,
    )
    address_label = models.CharField(max_length=255)
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ("sort_order", "name")

    def __str__(self):
        return self.name

# Potential conflict later, will resolve after Maman's PR :p
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

# Potential conflict later, will resolve after Maman's PR :p
class Listing(CoordinateModel):
    class ListingType(models.TextChoices):
        THRIFT = "thrift", "Thrift"
        BARTER = "barter", "Barter"

    store = models.ForeignKey(
        Store,
        on_delete=models.CASCADE,
        related_name="listings",
    )
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
