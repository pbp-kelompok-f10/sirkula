import logging

from django.db import transaction

from .models import WardrobeItemImage, WardrobePhotoCleanup


logger = logging.getLogger(__name__)


def queue_photo_cleanup(names):
    """Catat referensi sebelum mencoba menghapus file storage."""
    cleanup_ids = []
    with transaction.atomic():
        for name in dict.fromkeys(names):
            if not name:
                continue
            pending, _ = WardrobePhotoCleanup.objects.get_or_create(
                file_name=name,
            )
            cleanup_ids.append(pending.pk)
    return tuple(cleanup_ids)


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

                # Periksa semua pengguna; antrean lama tidak boleh
                # menghapus file yang masih dipakai suatu pakaian.
                if WardrobeItemImage.objects.filter(image=pending.file_name).exists():
                    logger.warning(
                        "Cleanup ditunda karena foto masih dipakai; cleanup_id=%s.",
                        cleanup_id,
                    )
                    continue

                storage.delete(pending.file_name)
                pending.delete()

        except Exception:
            logger.exception(
                "Cleanup foto Wardrobe gagal; "
                "antrean tetap disimpan untuk cleanup_id=%s.",
                cleanup_id,
            )
