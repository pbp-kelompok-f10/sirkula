from django.core.exceptions import ValidationError


MAX_PHOTO_SIZE = 5_000_000


def validate_photo_size(value):
    if value.size > MAX_PHOTO_SIZE:
        raise ValidationError(
            "Ukuran setiap foto maksimal 5 MB.", code="photo_too_large"
        )
