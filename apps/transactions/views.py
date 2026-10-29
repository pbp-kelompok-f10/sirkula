from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.html import format_html
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction as db_transaction
from decimal import Decimal

from apps.marketplace.models import Product

from .cart import Cart
from .models import Order, OrderItem, OrderStatusHistory, TransactionNotification


@login_required
def cart_detail(request):
    cart = Cart(request)
    context = {
        "cart": cart,
        "items": cart.get_items(),
        "total_price": cart.total_price,
    }
    return render(request, "cart.html", context)


@require_POST
@login_required
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
@login_required
def cart_remove(request, product_id):
    product = get_object_or_404(Product, pk=product_id)
    Cart(request).remove(product)
    messages.success(request, f"{product.name} dihapus dari keranjang.")
    return redirect("transactions:cart")


@require_POST
@login_required
def cart_clear(request):
    Cart(request).clear()
    messages.success(request, "Keranjang dikosongkan.")
    return redirect("transactions:cart")


SHIPPING_COSTS = {
    "FAST": Decimal("10000"),
    "REGULAR": Decimal("2500"),
    "ECONOMY": Decimal("0"),
}


@login_required
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
        with db_transaction.atomic():
            locked_items = list(
                Product.objects.select_for_update().filter(
                    pk__in=[item.pk for item in items],
                    is_available=True,
                    listing_type=Product.ListingType.THRIFT,
                )
            )
            if len(locked_items) != len(items):
                messages.error(request, "Salah satu produk sudah tidak tersedia.")
                return redirect("transactions:cart")
            subtotal = sum((item.price for item in locked_items), Decimal("0"))
            checkout_total = subtotal + admin_fee + shipping_cost
            buyer = request.user if request.user.is_authenticated else None
            order = Order.objects.create(
                buyer=buyer,
                address=address,
                phone_number=phone_number,
                purchase_method=purchase_method,
                shipping_method=shipping_method,
                shipping_cost=shipping_cost,
                admin_fee=admin_fee,
                subtotal=subtotal,
                total=checkout_total,
            )
            OrderItem.objects.bulk_create([
                OrderItem(order=order, product=item, price=item.price)
                for item in locked_items
            ])
            Product.objects.filter(pk__in=[item.pk for item in locked_items]).update(is_available=False)
            OrderStatusHistory.objects.create(
                order=order,
                status=Order.Status.PENDING,
                note="Pesanan dibuat.",
            )
        request.session.modified = True
        Cart(request).clear()
        request.session["checkout_success"] = {
            "order_id": order.pk,
            "total": str(checkout_total),
            "status": Order.Status.PENDING,
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


@login_required
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


@login_required
def thrift_success(request):
    checkout = request.session.pop("checkout_success", None)
    if not checkout:
        return redirect("transactions:cart")
    return render(request, "transactions/thrift_success.html", {
        "checkout": checkout,
    })


@login_required
def purchase_list(request):
    status = request.GET.get("status", "")
    transactions = Order.objects.filter(buyer=request.user)
    if status in Order.Status.values:
        transactions = transactions.filter(status=status)
    transactions = transactions.select_related("buyer").prefetch_related("items__product")
    page_obj = Paginator(transactions, 10).get_page(request.GET.get("page"))
    return render(request, "transactions/purchase_list.html", {
        "transactions": page_obj,
        "page_obj": page_obj,
        "statuses": Order.Status.choices,
        "selected_status": status,
    })


@login_required
def sales_list(request):
    status = request.GET.get("status", "")
    transactions = Order.objects.filter(items__product__seller=request.user).distinct()
    if status in Order.Status.values:
        transactions = transactions.filter(status=status)
    transactions = transactions.select_related("buyer").prefetch_related("items__product")
    page_obj = Paginator(transactions, 10).get_page(request.GET.get("page"))
    return render(request, "transactions/sales_list.html", {
        "transactions": page_obj,
        "page_obj": page_obj,
        "statuses": Order.Status.choices,
        "selected_status": status,
    })


@login_required
def transaction_detail(request, transaction_id):
    transaction = get_object_or_404(
        Order.objects.select_related("buyer"),
        pk=transaction_id,
    )
    is_buyer = transaction.buyer_id == request.user.id
    is_seller = transaction.items.filter(product__seller=request.user).exists()
    if not is_buyer and not is_seller:
        messages.error(request, "Kamu tidak memiliki akses ke transaksi ini.")
        return redirect("transactions:purchases")
    return render(request, "transactions/transaction_detail.html", {
        "transaction": transaction,
        "status_history": transaction.status_history.all(),
        "is_buyer": is_buyer,
        "is_seller": is_seller,
    })


@require_POST
@login_required
def update_transaction_status(request, transaction_id):
    transaction = get_object_or_404(
        Order.objects.select_related("buyer"),
        pk=transaction_id,
    )
    if not transaction.items.filter(product__seller=request.user).exists():
        messages.error(request, "Hanya penjual yang dapat mengubah status pesanan.")
        return redirect("transactions:detail", transaction_id=transaction.pk)

    next_status = request.POST.get("status")
    allowed_transitions = {
        Order.Status.PENDING: {
            Order.Status.CONFIRMED,
            Order.Status.CANCELLED,
        },
        Order.Status.CONFIRMED: {
            Order.Status.SHIPPED,
            Order.Status.CANCELLED,
        },
        Order.Status.SHIPPED: {Order.Status.COMPLETED},
    }
    if next_status not in allowed_transitions.get(transaction.status, set()):
        messages.error(request, "Perubahan status tidak valid.")
        return redirect("transactions:detail", transaction_id=transaction.pk)

    transaction.status = next_status
    transaction.save(update_fields=["status", "updated_at"])
    OrderStatusHistory.objects.create(
        order=transaction,
        status=next_status,
        note=f"Status diubah menjadi {transaction.get_status_display()}.",
    )
    if transaction.buyer_id:
        TransactionNotification.objects.create(
            recipient=transaction.buyer,
            order=transaction,
            message=f"Status order {transaction.order_number} berubah menjadi {transaction.get_status_display()}.",
        )
    messages.success(request, "Status transaksi berhasil diperbarui.")
    return redirect("transactions:detail", transaction_id=transaction.pk)
