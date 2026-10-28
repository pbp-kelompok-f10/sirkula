from django.contrib import admin

from .models import Product, ProductImage


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
