from django.core.validators import FileExtensionValidator
from rest_framework import serializers

from .models import Category, WardrobeItem, WardrobeItemImage
from .validators import validate_photo_size


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ("id", "name")

    def validate_name(self, value):
        value = value.strip()
        duplicates = Category.objects.filter(owner=self.context["request"].user, name__iexact=value)
        if self.instance:
            duplicates = duplicates.exclude(pk=self.instance.pk)
        if duplicates.exists():
            raise serializers.ValidationError("Kamu sudah memiliki kategori dengan nama ini.")
        return value


class PhotoSerializer(serializers.ModelSerializer):
    url = serializers.SerializerMethodField()

    class Meta:
        model = WardrobeItemImage
        fields = ("id", "position", "url")

    def get_url(self, obj):
        from django.urls import reverse
        return self.context["request"].build_absolute_uri(reverse("wardrobe_drf:photo", kwargs={"photo_id": obj.pk}))


class ItemSerializer(serializers.ModelSerializer):
    category = serializers.PrimaryKeyRelatedField(queryset=Category.objects.none(), allow_null=True, required=False)
    photos = serializers.ListField(child=serializers.ImageField(validators=[validate_photo_size, FileExtensionValidator(["jpg", "jpeg", "png", "webp"])]), write_only=True, required=False, max_length=5)
    delete_photos = serializers.ListField(child=serializers.IntegerField(min_value=1), write_only=True, required=False)
    images = PhotoSerializer(many=True, read_only=True)

    class Meta:
        model = WardrobeItem
        fields = ("id", "name", "status", "category", "images", "photos", "delete_photos", "created_at", "updated_at")
        read_only_fields = ("created_at", "updated_at")
        extra_kwargs = {"name": {"required": False, "allow_blank": True}, "status": {"required": False}}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["category"].queryset = Category.objects.filter(owner=self.context["request"].user)

    def validate_photos(self, photos):
        for photo in photos:
            if photo.image.format not in {"JPEG", "PNG", "WEBP"}:
                raise serializers.ValidationError("Format foto harus JPG, PNG, atau WebP.")
        return photos

    def validate(self, attrs):
        item = self.instance
        deleted = attrs.get("delete_photos", [])
        existing = list(item.images.all()) if item else []
        if len(deleted) != len(set(deleted)) or not set(deleted).issubset({photo.pk for photo in existing}):
            raise serializers.ValidationError({"delete_photos": "Pilih foto milik pakaian ini."})
        count = len(existing) - len(deleted) + len(attrs.get("photos", []))
        if count > 5:
            raise serializers.ValidationError({"photos": "Maksimal lima foto."})
        status = attrs.get("status", item.status if item else WardrobeItem.Status.ACTIVE)
        name = attrs.get("name", item.name if item else "").strip()
        category = attrs.get("category", item.category if item else None)
        if status == WardrobeItem.Status.ACTIVE and (not name or not category or not count):
            raise serializers.ValidationError("Pakaian aktif memerlukan nama, kategori, dan minimal satu foto.")
        if status == WardrobeItem.Status.DRAFT and not (name or category or count):
            raise serializers.ValidationError("Draft harus memiliki nama, kategori, atau foto.")
        if item and item.status == WardrobeItem.Status.ACTIVE and status == WardrobeItem.Status.DRAFT:
            raise serializers.ValidationError({"status": "Pakaian aktif tidak dapat dijadikan draft."})
        if status == WardrobeItem.Status.DRAFT:
            drafts = WardrobeItem.objects.filter(owner=self.context["request"].user, status=status)
            if item:
                drafts = drafts.exclude(pk=item.pk)
            if drafts.exists():
                raise serializers.ValidationError({"status": "Hanya satu draft diperbolehkan."})
        if "name" in attrs:
            attrs["name"] = name
        return attrs
