from pathlib import Path
from uuid import uuid4

from django.conf import settings
from django.db import models
from django.core.validators import FileExtensionValidator, MaxValueValidator, MinValueValidator

from .storage import PrivateWardrobeStorage
from .validators import validate_photo_size
from django.db.models.functions import Lower

# Create your models here.

class Category(models.Model):
    name = models.CharField(max_length=100)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="wardrobe_categories",
    )

    class Meta:
        db_table = "main_category"
        ordering = ["name", "id"]
        constraints = [
            models.UniqueConstraint(
                Lower("name"),
                models.F("owner"),
                name="unique_wardrobe_category_name_per_owner",
            ),
        ]

    def __str__(self):
        return self.name

class WardrobeItem(models.Model):
    name = models.CharField(max_length=100)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="wardrobe_items",
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="items",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return self.name



def wardrobe_photo_path(instance, filename):
    extension = Path(filename).suffix.lower()
    return f"photos/{uuid4().hex}{extension}"


class WardrobeItemImage(models.Model):
    item = models.ForeignKey(
        WardrobeItem, on_delete=models.CASCADE, related_name="images"
    )
    image = models.ImageField(
        storage=PrivateWardrobeStorage(),
        upload_to=wardrobe_photo_path,
        validators=[
            validate_photo_size,
            FileExtensionValidator(allowed_extensions=["jpg", "jpeg", "png", "webp"]),
        ],
    )
    position = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )

    class Meta:
        ordering = ["position", "id"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(position__gte=1, position__lte=5),
                name="wardrobe_image_position_1_to_5",
            ),
            models.UniqueConstraint(
                fields=["item", "position"], name="wardrobe_unique_image_position"
            ),
        ]

    def __str__(self):
        return f"{self.item.name} - Foto {self.position}"


class WardrobePhotoCleanup(models.Model):
    file_name = models.CharField(max_length=100, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "pk"]
