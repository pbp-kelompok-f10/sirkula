from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.html import format_html
from django.views.decorators.http import require_POST

from apps.marketplace.models import Product

from .cart import Cart


def cart_detail(request):
    cart = Cart(request)
    context = {
        "cart": cart,
        "items": cart.get_items(),
        "total_price": cart.total_price,
    }
    return render(request, "cart.html", context)


@require_POST
def cart_add(request, product_id):
    product = get_object_or_404(Product, pk=product_id)

    if product.listing_type != Product.ListingType.THRIFT:
        messages.error(
            request,
            f"{product.name} adalah barang barter, tidak bisa dibeli.",
        )
        return redirect("marketplace:product_detail", pk=product.pk)

    if not product.is_available:
        messages.error(request, f"{product.name} sudah tidak tersedia.")
        return redirect("marketplace:product_detail", pk=product.pk)

    cart = Cart(request)
    if product in cart:
        messages.info(request, f"{product.name} sudah ada di keranjang.")
    else:
        cart.add(product)
        messages.success(
            request,
            format_html(
                '{} masuk ke keranjang. '
                '<a href="{}" class="underline font-bold">Lihat keranjang</a>',
                product.name,
                reverse("transactions:cart"),
            ),
        )

    return redirect("marketplace:product_detail", pk=product.pk)


@require_POST
def cart_remove(request, product_id):
    product = get_object_or_404(Product, pk=product_id)
    Cart(request).remove(product)
    messages.success(request, f"{product.name} dihapus dari keranjang.")
    return redirect("transactions:cart")


@require_POST
def cart_clear(request):
    Cart(request).clear()
    messages.success(request, "Keranjang dikosongkan.")
    return redirect("transactions:cart")
