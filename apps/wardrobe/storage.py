from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.utils.deconstruct import deconstructible


@deconstructible
class PrivateWardrobeStorage(FileSystemStorage):
    def __init__(self):
        super().__init__(
            directory_permissions_mode=0o700,
            file_permissions_mode=0o600,
        )

    @property
    def base_location(self):
        return str(settings.WARDROBE_PRIVATE_ROOT)

    @property
    def location(self):
        return self.base_location

    def url(self, name):
        raise NotImplementedError(
            "Foto Wardrobe harus diakses melalui endpoint yang memeriksa pemilik."
        )
