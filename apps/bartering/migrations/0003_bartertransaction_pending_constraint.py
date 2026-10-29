from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("bartering", "0002_barteroffer_shipping"),
    ]

    operations = [
        migrations.AddConstraint(
            model_name="barteroffer",
            constraint=models.UniqueConstraint(
                condition=models.Q(status="PENDING"),
                fields=("proposer", "requested_product", "offered_product"),
                name="one_pending_offer_per_product_pair",
            ),
        ),
        migrations.CreateModel(
            name="BarterTransaction",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                (
                    "offer",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="transaction",
                        to="bartering.barteroffer",
                    ),
                ),
                (
                    "proposer",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="barter_transactions_as_proposer",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "recipient",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="barter_transactions_as_recipient",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
        ),
    ]
