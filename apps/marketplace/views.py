from django.shortcuts import get_object_or_404, render
from django.core.paginator import Paginator

from .models import Product


def show_shop(request):
    products = (
        Product.objects.filter(is_available=True)
        .select_related("seller")
    )
    query = request.GET.get("q", "").strip()
    min_price = request.GET.get("min_price", "").strip()
    max_price = request.GET.get("max_price", "").strip()
    size = request.GET.get("size", "").strip()
    location = request.GET.get("location", "").strip()

    if query:
        products = products.filter(name__icontains=query)
    if min_price.isdigit():
        products = products.filter(price__gte=min_price)
    if max_price.isdigit():
        products = products.filter(price__lte=max_price)
    if size:
        products = products.filter(size__iexact=size)
    if location:
        products = products.filter(location__icontains=location)

    paginator = Paginator(products, 9)
    page_obj = paginator.get_page(request.GET.get("page"))
    return render(request, "shop.html", {
        "products": page_obj,
        "page_obj": page_obj,
        "query": query,
        "min_price": min_price,
        "max_price": max_price,
        "selected_size": size,
        "location": location,
    })


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
