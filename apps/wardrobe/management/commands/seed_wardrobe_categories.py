from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import connections

from apps.wardrobe.defaults import ensure_default_categories


class Command(BaseCommand):
    help = "Lengkapi kategori default semua pengguna tanpa menggandakan nama beda kapital."

    def add_arguments(self, parser):
        parser.add_argument(
            "--database", default="default", choices=tuple(connections),
            help="Database pengguna dan kategori (default: default).",
        )

    def handle(self, *args, **options):
        using = options["database"]
        owner_ids = (
            get_user_model()._default_manager.using(using)
            .order_by("pk").values_list("pk", flat=True)
        )
        users = 0
        categories = 0
        for owner_id in owner_ids.iterator(chunk_size=500):
            categories += ensure_default_categories(owner_id, using=using)
            users += 1
        self.stdout.write(self.style.SUCCESS(
            f"Pengguna diproses: {users}; kategori ditambahkan: {categories}."
        ))
