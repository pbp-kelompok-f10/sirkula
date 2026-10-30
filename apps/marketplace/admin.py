from django.contrib import admin

from .models import Listing, PredefinedLocation, Store


@admin.register(PredefinedLocation)
class PredefinedLocationAdmin(admin.ModelAdmin):
    list_display = ("name", "region_type", "latitude", "longitude", "is_active")
    list_filter = ("region_type", "is_active")
    list_editable = ("is_active",)
    search_fields = ("name", "address_label")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Store)
class StoreAdmin(admin.ModelAdmin):
    list_display = ("name", "address", "latitude", "longitude", "is_active")
    list_filter = ("is_active",)
    list_editable = ("is_active",)
    search_fields = ("name", "address", "description")
    prepopulated_fields = {"slug": ("name",)}
    raw_id_fields = ("owner",)


@admin.register(Listing)
class ListingAdmin(admin.ModelAdmin):
    list_display = ("title", "store", "listing_type", "price", "is_available")
    list_filter = ("listing_type", "is_available", "store")
    list_editable = ("is_available",)
    search_fields = ("title", "description", "store__name")
    prepopulated_fields = {"slug": ("title",)}
    raw_id_fields = ("seller",)
