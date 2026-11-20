from rest_framework import serializers

from .models import PredefinedLocation, Product, ProductImage, SavedPlace


class ProductImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductImage
        fields = ("id", "image", "order")
        read_only_fields = ("id",)


class ProductSerializer(serializers.ModelSerializer):
    gallery = ProductImageSerializer(many=True, read_only=True)
    barter_wanted_list = serializers.ReadOnlyField()
    seller = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = Product
        fields = (
            "id", "seller", "listing_type", "name", "brand", "size", "price",
            "image", "description", "usage_duration", "barter_reason",
            "barter_wanted", "barter_wanted_list", "location", "is_available",
            "gallery", "created_at", "updated_at",
        )
        read_only_fields = ("id", "seller", "created_at", "updated_at")


class SavedPlaceSerializer(serializers.ModelSerializer):
    class Meta:
        model = SavedPlace
        fields = ("id", "name", "address_label", "notes", "latitude", "longitude", "created_at", "updated_at")
        read_only_fields = ("id", "created_at", "updated_at")


class PredefinedLocationSerializer(serializers.ModelSerializer):
    address = serializers.CharField(source="address_label", read_only=True)

    class Meta:
        model = PredefinedLocation
        fields = ("name", "slug", "region_type", "address", "latitude", "longitude")
