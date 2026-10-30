from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver

from .defaults import ensure_default_categories


@receiver(post_save, sender=settings.AUTH_USER_MODEL, dispatch_uid="wardrobe.default_categories")
def create_default_categories(sender, instance, created, raw=False, using="default", **kwargs):
    if created and not raw:
        ensure_default_categories(instance.pk, using=using)
