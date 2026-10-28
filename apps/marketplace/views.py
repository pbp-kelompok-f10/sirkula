from django.shortcuts import get_object_or_404, render

from .models import Product


def show_shop(request):
    products = (
        Product.objects.filter(is_available=True)
        .select_related("seller")
    )
    return render(request, "shop.html", {"products": products})


def product_detail(request, pk):
    product = get_object_or_404(
        Product.objects.select_related("seller").prefetch_related("gallery"),
        pk=pk,
    )

    related_barter = (
        Product.objects.filter(
            listing_type=Product.ListingType.BARTER,
            is_available=True,
        )
        .exclude(pk=product.pk)
        .select_related("seller")[:4]
    )
    related_thrift = (
        Product.objects.filter(
            listing_type=Product.ListingType.THRIFT,
            is_available=True,
        )
        .exclude(pk=product.pk)
        .select_related("seller")[:4]
    )

    context = {
        "product": product,
        "related_barter": related_barter,
        "related_thrift": related_thrift,
    }
    return render(request, "product_detail.html", context)
