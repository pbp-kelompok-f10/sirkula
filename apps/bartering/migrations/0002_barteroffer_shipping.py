from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("bartering", "0001_initial")]
    operations = [
        migrations.AddField(model_name="barteroffer", name="proposer_tracking_number", field=models.CharField(blank=True, max_length=100)),
        migrations.AddField(model_name="barteroffer", name="recipient_tracking_number", field=models.CharField(blank=True, max_length=100)),
        migrations.AddField(model_name="barteroffer", name="proposer_received", field=models.BooleanField(default=False)),
        migrations.AddField(model_name="barteroffer", name="recipient_received", field=models.BooleanField(default=False)),
        migrations.AlterField(model_name="barteroffer", name="status", field=models.CharField(choices=[("PENDING", "Menunggu keputusan"), ("ACCEPTED", "Diterima"), ("SHIPPING", "Dalam pengiriman"), ("COMPLETED", "Selesai"), ("REJECTED", "Ditolak"), ("CANCELLED", "Dibatalkan")], default="PENDING", max_length=10)),
    ]
