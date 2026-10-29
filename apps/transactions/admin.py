from django.contrib import admin

from .models import Transaction


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "product",
        "buyer",
        "purchase_method",
        "status",
        "total",
        "created_at",
    )
    list_filter = ("status", "purchase_method", "shipping_method")
    search_fields = ("product__name", "buyer__username", "phone_number")
    readonly_fields = ("created_at", "updated_at")
