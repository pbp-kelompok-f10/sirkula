from django.contrib import admin

from .models import BarterOffer, BarterTransaction


@admin.register(BarterOffer)
class BarterOfferAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "proposer",
        "recipient",
        "requested_product",
        "offered_product",
        "status",
        "created_at",
    )
    list_filter = ("status",)
    search_fields = (
        "proposer__username",
        "recipient__username",
        "requested_product__name",
        "offered_product__name",
    )


@admin.register(BarterTransaction)
class BarterTransactionAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "offer",
        "proposer",
        "recipient",
        "created_at",
        "completed_at",
    )
    list_filter = ("completed_at", "created_at")
    search_fields = ("proposer__username", "recipient__username")
