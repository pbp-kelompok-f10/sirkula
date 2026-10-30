from django.core.management.base import BaseCommand, CommandError
from django.db.models import Max

from apps.wardrobe.cleanup import cleanup_pending_photos
from apps.wardrobe.models import WardrobePhotoCleanup


class Command(BaseCommand):
    help = "Coba ulang penghapusan file foto Wardrobe yang masih tercatat dalam antrean."

    def add_arguments(self, parser):
        parser.add_argument(
            "--batch-size", type=int, default=100,
            help="Jumlah antrean per batch (default: 100).",
        )

    def handle(self, *args, **options):
        batch_size = options["batch_size"]
        if batch_size < 1:
            raise CommandError("--batch-size harus lebih besar dari nol.")

        # Batasi pada antrean saat command mulai; antrean baru diproses run berikutnya.
        upper_pk = WardrobePhotoCleanup.objects.aggregate(value=Max("pk"))["value"]
        if upper_pk is None:
            self.stdout.write("Tidak ada antrean cleanup foto Wardrobe.")
            return

        last_pk = 0
        processed = 0
        remaining = 0
        while True:
            ids = list(
                WardrobePhotoCleanup.objects
                .filter(pk__gt=last_pk, pk__lte=upper_pk)
                .order_by("pk")
                .values_list("pk", flat=True)[:batch_size]
            )
            if not ids:
                break

            cleanup_pending_photos(ids)
            processed += len(ids)
            remaining += WardrobePhotoCleanup.objects.filter(pk__in=ids).count()
            last_pk = ids[-1]

        self.stdout.write(
            f"Diproses: {processed}; selesai: {processed - remaining}; "
            f"masih tertunda: {remaining}."
        )
        if remaining:
            raise CommandError(
                "Masih ada file yang belum dibersihkan. "
                "Referensi tetap disimpan; periksa log lalu jalankan ulang command."
            )
