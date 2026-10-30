from django.contrib import admin

from .models import Listing, PredefinedLocation, Product, ProductImage, Store


class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 3


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "listing_type",
        "price",
        "seller",
        "is_available",
        "created_at",
    )
    list_filter = ("listing_type", "is_available", "created_at")
    search_fields = ("name", "seller__username")
    inlines = (ProductImageInline,)
    ordering = ("-created_at",)


@admin.register(PredefinedLocation)
class PredefinedLocationAdmin(admin.ModelAdmin):
    list_display = ("name", "region_type", "is_active", "sort_order")
    list_filter = ("region_type", "is_active")
    search_fields = ("name", "address_label", "slug")


@admin.register(SavedPlace)
class SavedPlaceAdmin(admin.ModelAdmin):
    list_display = ("name", "user", "address_label", "latitude", "longitude", "updated_at")
    list_filter = ("created_at", "updated_at")
    search_fields = ("name", "address_label", "notes", "user__username")
    raw_id_fields = ("user",)
    readonly_fields = ("created_at", "updated_at")


@admin.register(Store)
class StoreAdmin(admin.ModelAdmin):
    list_display = ("name", "owner", "address", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name", "address", "slug")


@admin.register(Listing)
class ListingAdmin(admin.ModelAdmin):
    list_display = ("title", "listing_type", "store", "seller", "price", "is_available")
    list_filter = ("listing_type", "is_available")
    search_fields = ("title", "slug", "store__name")
