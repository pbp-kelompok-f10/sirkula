from django.contrib import admin

from .models import (
    Order,
    OrderItem,
    OrderStatusHistory,
    Transaction,
    TransactionNotification,
)


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


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("id", "buyer", "status", "purchase_method", "total", "created_at")
    list_filter = ("status", "purchase_method", "shipping_method")
    search_fields = ("buyer__username", "phone_number")
    readonly_fields = ("created_at", "updated_at")


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ("order", "product", "price")
    search_fields = ("order__buyer__username", "product__name")


@admin.register(OrderStatusHistory)
class OrderStatusHistoryAdmin(admin.ModelAdmin):
    list_display = ("order", "status", "created_at")
    list_filter = ("status",)


@admin.register(TransactionNotification)
class TransactionNotificationAdmin(admin.ModelAdmin):
    list_display = ("recipient", "order", "is_read", "created_at")
    list_filter = ("is_read",)
