from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.marketplace.models import Product


ITEMS = (
    ("Jaket Denim", "Levi's", "L", "8 bulan"),
    ("Kemeja Linen", "Uniqlo", "M", "5 bulan"),
    ("Sweater Rajut", "H&M", "L", "1 tahun"),
    ("Celana Chino", "Erigo", "32", "7 bulan"),
    ("Blazer Klasik", "Zara", "M", "10 bulan"),
    ("Rok Midi", "Cotton Ink", "S", "6 bulan"),
    ("Hoodie Oversize", "Pull&Bear", "XL", "9 bulan"),
    ("Kaos Katun", "Muji", "M", "4 bulan"),
    ("Cardigan Rajut", "Mango", "L", "11 bulan"),
    ("Dress Kasual", "This Is April", "M", "6 bulan"),
)

VARIANTS = (
    ("Vintage", "Biru", 0),
    ("Minimalis", "Krem", 20_000),
    ("Retro", "Hijau", 35_000),
    ("Klasik", "Hitam", 50_000),
    ("Premium", "Cokelat", 75_000),
)

LOCATIONS = (
    "Jakarta Pusat",
    "Jakarta Selatan",
    "Jakarta Timur",
    "Depok",
    "Kota Bogor",
    "Bekasi",
    "Tangerang",
    "Tangerang Selatan",
)


def build_product_rows(count):
    """Return deterministic mock product dictionaries."""
    rows = []
    for index in range(count):
        item, brand, size, usage_duration = ITEMS[index % len(ITEMS)]
        variant, colour, surcharge = VARIANTS[(index // len(ITEMS)) % len(VARIANTS)]
        number = index + 1
        is_barter = number % 4 == 0
        rows.append({
            "name": f"{item} {variant} {colour} #{number:02d}",
            "brand": brand,
            "size": size,
            "price": Decimal("0") if is_barter else Decimal(55_000 + (index % 10) * 15_000 + surcharge),
            "listing_type": Product.ListingType.BARTER if is_barter else Product.ListingType.THRIFT,
            "description": (
                f"{item} preloved warna {colour.lower()} dalam kondisi terawat. "
                "Sudah dibersihkan dan siap dipakai kembali."
            ),
            "usage_duration": usage_duration,
            "barter_reason": "Ingin memberi ruang di lemari dan memperpanjang usia pakai barang." if is_barter else "",
            "barter_wanted": "Tote bag\nOuter kasual\nAksesori" if is_barter else "",
            "location": LOCATIONS[index % len(LOCATIONS)],
            "is_available": True,
        })
    return rows


class Command(BaseCommand):
    help = "Seed produk marketplace mockup tanpa membuat akun baru."

    def add_arguments(self, parser):
        parser.add_argument(
            "--seller",
            help="Username akun yang akan menjadi pemilik produk. Default: akun aktif pertama.",
        )
        parser.add_argument(
            "--count",
            type=int,
            default=50,
            help="Jumlah produk mockup (default: 50, maksimum: 500).",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        count = options["count"]
        if not 1 <= count <= 500:
            raise CommandError("--count harus berada di antara 1 dan 500.")

        users = get_user_model()._default_manager.filter(is_active=True)
        username = options.get("seller")
        if username:
            seller = users.filter(username=username).first()
            if seller is None:
                raise CommandError(f'Akun aktif dengan username "{username}" tidak ditemukan.')
        else:
            seller = users.order_by("-is_superuser", "pk").first()
            if seller is None:
                raise CommandError(
                    "Belum ada akun aktif. Buat/daftarkan akun terlebih dahulu; command ini tidak membuat akun."
                )

        created = 0
        updated = 0
        for row in build_product_rows(count):
            _, was_created = Product.objects.update_or_create(
                seller=seller,
                name=row.pop("name"),
                defaults=row,
            )
            created += int(was_created)
            updated += int(not was_created)

        self.stdout.write(self.style.SUCCESS(
            f"Seed selesai untuk @{seller.username}: {created} dibuat, {updated} diperbarui; total {count} produk mockup."
        ))
