from django.conf import settings
from django.db import models
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
