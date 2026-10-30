from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("transactions", "0001_initial"),
        ("marketplace", "0003_product_barter_reason_product_barter_wanted_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="Order",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("address", models.CharField(max_length=255)),
                ("phone_number", models.CharField(max_length=30)),
                ("purchase_method", models.CharField(choices=[("COD", "Cash on Delivery"), ("PICKUP", "Pickup")], max_length=10)),
                ("shipping_method", models.CharField(max_length=10)),
                ("shipping_cost", models.DecimalField(decimal_places=0, default=0, max_digits=10)),
                ("admin_fee", models.DecimalField(decimal_places=0, default=0, max_digits=10)),
                ("subtotal", models.DecimalField(decimal_places=0, max_digits=10)),
                ("total", models.DecimalField(decimal_places=0, max_digits=10)),
                ("status", models.CharField(choices=[("PENDING", "Menunggu konfirmasi"), ("CONFIRMED", "Dikonfirmasi"), ("SHIPPED", "Dikirim"), ("COMPLETED", "Selesai"), ("CANCELLED", "Dibatalkan")], default="PENDING", max_length=12)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("buyer", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="orders", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="OrderItem",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("price", models.DecimalField(decimal_places=0, max_digits=10)),
                ("order", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="items", to="transactions.order")),
                ("product", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="order_items", to="marketplace.product")),
            ],
        ),
    ]
