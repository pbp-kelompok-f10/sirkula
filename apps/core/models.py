from django.conf import settings
from django.core.validators import MinLengthValidator
from django.db import models


class Review(models.Model):
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="website_reviews"
    )
    is_superuser_submission = models.BooleanField(default=False, editable=False)
    content = models.TextField(max_length=1000, validators=[MinLengthValidator(10)])
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "-pk"]
        constraints = [
            models.UniqueConstraint(
                fields=["author"], condition=models.Q(is_superuser_submission=False),
                name="core_one_regular_review_per_author",
            )
        ]

    def __str__(self):
        return f"Website review by {self.author_id}"


class ReviewLike(models.Model):
    review = models.ForeignKey(Review, on_delete=models.CASCADE, related_name="likes")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="website_review_likes"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["review", "user"], name="core_unique_review_like")
        ]
