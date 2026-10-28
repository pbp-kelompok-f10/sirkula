from django.contrib import admin

from .models import Product


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("name", "price", "seller", "is_available", "created_at")
    list_filter = ("is_available", "created_at")
    search_fields = ("name", "seller__username")
    ordering = ("-created_at",)
