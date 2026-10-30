from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("marketplace", "0003_product_barter_reason_product_barter_wanted_and_more"),
    ]
    operations = [
        migrations.CreateModel(
            name="BarterOffer",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("message", models.TextField(blank=True)),
                ("status", models.CharField(choices=[("PENDING", "Menunggu keputusan"), ("ACCEPTED", "Diterima"), ("REJECTED", "Ditolak"), ("CANCELLED", "Dibatalkan")], default="PENDING", max_length=10)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("offered_product", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="barter_offers_sent", to="marketplace.product")),
                ("proposer", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="barter_offers_sent", to=settings.AUTH_USER_MODEL)),
                ("recipient", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="barter_offers_received", to=settings.AUTH_USER_MODEL)),
                ("requested_product", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="barter_offers_received", to="marketplace.product")),
            ],
            options={"ordering": ["-created_at"]},
        ),
    ]
