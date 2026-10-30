from django.db import migrations, models
import django.db.models.deletion
import apps.transactions.models


class Migration(migrations.Migration):
    dependencies = [
        ("transactions", "0002_order_orderitem"),
    ]
    operations = [
        migrations.AddField(
            model_name="order",
            name="order_number",
            field=models.CharField(default=apps.transactions.models.generate_order_number, max_length=32, unique=True),
        ),
        migrations.CreateModel(
            name="OrderStatusHistory",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("status", models.CharField(choices=[("PENDING", "Menunggu konfirmasi"), ("CONFIRMED", "Dikonfirmasi"), ("SHIPPED", "Dikirim"), ("COMPLETED", "Selesai"), ("CANCELLED", "Dibatalkan")], max_length=12)),
                ("note", models.CharField(blank=True, max_length=255)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("order", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="status_history", to="transactions.order")),
            ],
            options={"ordering": ["created_at"]},
        ),
        migrations.CreateModel(
            name="TransactionNotification",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("message", models.CharField(max_length=255)),
                ("is_read", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("order", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="notifications", to="transactions.order")),
                ("recipient", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="transaction_notifications", to="auth.user")),
            ],
        ),
    ]
