# Generated manually for Django 5.2 because the local environment may not have
# optional frontend dependencies installed when migrations are created.

import decimal

import django.core.validators
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="PredefinedLocation",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("latitude", models.DecimalField(decimal_places=6, max_digits=9, validators=[django.core.validators.MinValueValidator(decimal.Decimal("-90")), django.core.validators.MaxValueValidator(decimal.Decimal("90"))])),
                ("longitude", models.DecimalField(decimal_places=6, max_digits=9, validators=[django.core.validators.MinValueValidator(decimal.Decimal("-180")), django.core.validators.MaxValueValidator(decimal.Decimal("180"))])),
                ("slug", models.SlugField(max_length=80, unique=True)),
                ("name", models.CharField(max_length=120)),
                ("region_type", models.CharField(choices=[("city", "Kota"), ("regency", "Kabupaten")], default="city", max_length=16)),
                ("address_label", models.CharField(max_length=255)),
                ("is_active", models.BooleanField(default=True)),
                ("sort_order", models.PositiveSmallIntegerField(default=0)),
            ],
            options={"ordering": ("sort_order", "name")},
        ),
        migrations.CreateModel(
            name="Store",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("latitude", models.DecimalField(decimal_places=6, max_digits=9, validators=[django.core.validators.MinValueValidator(decimal.Decimal("-90")), django.core.validators.MaxValueValidator(decimal.Decimal("90"))])),
                ("longitude", models.DecimalField(decimal_places=6, max_digits=9, validators=[django.core.validators.MinValueValidator(decimal.Decimal("-180")), django.core.validators.MaxValueValidator(decimal.Decimal("180"))])),
                ("name", models.CharField(max_length=150)),
                ("slug", models.SlugField(max_length=170, unique=True)),
                ("description", models.TextField(blank=True)),
                ("address", models.CharField(max_length=255)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("owner", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="marketplace_stores", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ("name",)},
        ),
        migrations.CreateModel(
            name="Listing",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("latitude", models.DecimalField(decimal_places=6, max_digits=9, validators=[django.core.validators.MinValueValidator(decimal.Decimal("-90")), django.core.validators.MaxValueValidator(decimal.Decimal("90"))])),
                ("longitude", models.DecimalField(decimal_places=6, max_digits=9, validators=[django.core.validators.MinValueValidator(decimal.Decimal("-180")), django.core.validators.MaxValueValidator(decimal.Decimal("180"))])),
                ("listing_type", models.CharField(choices=[("thrift", "Thrift"), ("barter", "Barter")], max_length=10)),
                ("title", models.CharField(max_length=180)),
                ("slug", models.SlugField(max_length=200, unique=True)),
                ("description", models.TextField(blank=True)),
                ("price", models.DecimalField(blank=True, decimal_places=2, help_text="Required for thrift listings; optional for barter listings.", max_digits=12, null=True)),
                ("image_url", models.URLField(blank=True, max_length=500)),
                ("is_available", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("seller", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="marketplace_listings", to=settings.AUTH_USER_MODEL)),
                ("store", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="listings", to="marketplace.store")),
            ],
            options={"ordering": ("-created_at",)},
        ),
    ]
