from django.contrib import admin

from .models import BarterOffer


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
