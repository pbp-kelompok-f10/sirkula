from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("transactions", "0003_order_history_notifications")]

    operations = [
        migrations.AddField(
            model_name="order",
            name="paid_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="order",
            name="payment_qr_url",
            field=models.URLField(blank=True),
        ),
        migrations.AddField(
            model_name="order",
            name="payment_status",
            field=models.CharField(default="PENDING", max_length=20),
        ),
        migrations.AddField(
            model_name="order",
            name="payment_transaction_id",
            field=models.CharField(blank=True, max_length=100),
        ),
    ]
