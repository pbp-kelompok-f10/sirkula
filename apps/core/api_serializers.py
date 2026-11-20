from rest_framework import serializers

from .models import Review


class ReviewSerializer(serializers.ModelSerializer):
    author = serializers.ReadOnlyField(source="author.username")
    like_count = serializers.IntegerField(source="likes.count", read_only=True)
    content = serializers.CharField(min_length=10, max_length=1000, trim_whitespace=True)

    class Meta:
        model = Review
        fields = ("id", "author", "content", "like_count", "created_at", "updated_at")
        read_only_fields = ("id", "author", "like_count", "created_at", "updated_at")
