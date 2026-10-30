"""Initial categories shared by user creation and the explicit backfill command."""
from django.contrib.auth import get_user_model
from django.db import transaction

from .models import Category


DEFAULT_CATEGORY_NAMES = ("Kaos", "Celana", "Kemeja", "Outer", "Sepatu")


def ensure_default_categories(owner_id, *, using="default"):
    created_count = 0
    with transaction.atomic(using=using):
        # Serialize backfills for the same owner; the database also enforces uniqueness.
        get_user_model()._default_manager.using(using).select_for_update().get(pk=owner_id)
        categories = Category.objects.using(using)
        for name in DEFAULT_CATEGORY_NAMES:
            _, created = categories.get_or_create(
                owner_id=owner_id,
                name__iexact=name,
                defaults={"name": name},
            )
            created_count += int(created)
    return created_count
