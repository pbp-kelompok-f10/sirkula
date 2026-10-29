from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.html import format_html
from django.views.decorators.http import require_POST
from decimal import Decimal

from apps.marketplace.models import Product

from .cart import Cart
from .models import Transaction


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


SHIPPING_COSTS = {
    "FAST": Decimal("10000"),
    "REGULAR": Decimal("2500"),
    "ECONOMY": Decimal("0"),
}


def thrift_checkout(request):
    cart = Cart(request)
    items = cart.get_items()
    if not items:
        messages.info(request, "Keranjang masih kosong.")
        return redirect("transactions:cart")

    if request.method == "POST":
        shipping_method = request.POST.get("shipping_method", "REGULAR")
        if shipping_method not in SHIPPING_COSTS:
            messages.error(request, "Pilihan pengiriman tidak valid.")
            return redirect("transactions:thrift_checkout")

        address = request.POST.get("address", "").strip()
        phone_number = request.POST.get("phone_number", "").strip()
        purchase_method = request.POST.get("purchase_method", "COD")
        if purchase_method not in {"COD", "PICKUP"}:
            messages.error(request, "Metode pembelian tidak valid.")
            return redirect("transactions:thrift_checkout")
        if not address or not phone_number:
            messages.error(request, "Alamat dan nomor handphone wajib diisi.")
            return redirect("transactions:thrift_checkout")

        admin_fee = Decimal("1000")
        shipping_cost = SHIPPING_COSTS[shipping_method]
        checkout_total = cart.total_price + admin_fee + shipping_cost
        request.session["checkout"] = {
            "address": address,
            "phone_number": phone_number,
            "shipping_method": shipping_method,
            "shipping_cost": str(shipping_cost),
            "purchase_method": purchase_method,
            "subtotal": str(cart.total_price),
            "admin_fee": str(admin_fee),
            "total": str(checkout_total),
        }
        buyer = request.user if request.user.is_authenticated else None
        transactions = Transaction.objects.bulk_create([
            Transaction(
                buyer=buyer,
                product=item,
                address=address,
                phone_number=phone_number,
                purchase_method=purchase_method,
                shipping_method=shipping_method,
                shipping_cost=shipping_cost,
                admin_fee=admin_fee,
                subtotal=item.price,
                total=item.price + admin_fee + shipping_cost,
            )
            for item in items
        ])
        Product.objects.filter(pk__in=[item.pk for item in items]).update(is_available=False)
        request.session.modified = True
        Cart(request).clear()
        request.session["checkout_success"] = {
            "transaction_ids": [transaction.pk for transaction in transactions],
            "total": str(checkout_total),
            "status": Transaction.Status.PENDING,
        }
        request.session.pop("checkout", None)
        return redirect("transactions:thrift_success")

    admin_fee = Decimal("1000")
    shipping_cost = SHIPPING_COSTS["REGULAR"]
    checkout_total = cart.total_price + admin_fee + shipping_cost
    return render(request, "transactions/thrift_checkout.html", {
        "items": items,
        "total_price": cart.total_price,
        "admin_fee": admin_fee,
        "shipping_cost": shipping_cost,
        "checkout_total": checkout_total,
    })


def thrift_payment(request):
    checkout = request.session.get("checkout")
    if not checkout:
        return redirect("transactions:thrift_checkout")

    if request.method == "POST":
        Cart(request).clear()
        request.session["checkout_success"] = checkout
        request.session.pop("checkout", None)
        return redirect("transactions:thrift_success")

    return render(request, "transactions/thrift_payment.html", {
        "checkout_total": Decimal(checkout["total"]),
    })


def thrift_success(request):
    checkout = request.session.pop("checkout_success", None)
    if not checkout:
        return redirect("transactions:cart")
    return render(request, "transactions/thrift_success.html", {
        "checkout": checkout,
    })
