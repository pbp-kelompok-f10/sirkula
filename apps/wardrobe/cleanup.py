import logging

from django.db import transaction

from .models import WardrobeItemImage, WardrobePhotoCleanup


logger = logging.getLogger(__name__)


def cleanup_pending_photos(cleanup_ids):
    storage = WardrobeItemImage._meta.get_field("image").storage

    for cleanup_id in cleanup_ids:
        try:
            with transaction.atomic():
                pending = (
                    WardrobePhotoCleanup.objects
                    .select_for_update()
                    .filter(pk=cleanup_id)
                    .first()
                )

                if pending is None:
                    continue

                storage.delete(pending.file_name)

                # Hanya hapus antrean setelah storage berhasil.
                pending.delete()

        except Exception:
            logger.exception(
                "Cleanup foto Wardrobe gagal; "
                "antrean tetap disimpan untuk cleanup_id=%s.",
                cleanup_id,
            )
