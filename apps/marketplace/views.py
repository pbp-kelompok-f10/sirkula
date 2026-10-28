from django.shortcuts import render

from .models import Product


def show_shop(request):
    products = (
        Product.objects.filter(is_available=True)
        .select_related("seller")
    )
    return render(request, "shop.html", {"products": products})
