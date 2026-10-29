from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from django.core.paginator import Paginator

from .models import Product
from .forms import ProductForm, ProductImageFormSet


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


@login_required
def seller_products(request):
    products = Product.objects.filter(seller=request.user)
    return render(request, "marketplace/seller_products.html", {"products": products})


@login_required
def product_create(request):
    product = Product(seller=request.user)
    form = ProductForm(request.POST or None, request.FILES or None, instance=product)
    image_formset = ProductImageFormSet(
        request.POST or None,
        request.FILES or None,
        instance=product,
    )
    if request.method == "POST" and form.is_valid() and image_formset.is_valid():
        product = form.save(commit=False)
        product.seller = request.user
        product.save()
        image_formset.instance = product
        image_formset.save()
        messages.success(request, "Produk berhasil ditambahkan.")
        return redirect("marketplace:seller_products")
    return render(request, "marketplace/product_form.html", {
        "form": form,
        "image_formset": image_formset,
        "page_title": "Tambah Produk",
    })


@login_required
def product_update(request, pk):
    product = get_object_or_404(Product, pk=pk, seller=request.user)
    form = ProductForm(request.POST or None, request.FILES or None, instance=product)
    image_formset = ProductImageFormSet(
        request.POST or None,
        request.FILES or None,
        instance=product,
    )
    if request.method == "POST" and form.is_valid() and image_formset.is_valid():
        form.save()
        image_formset.save()
        messages.success(request, "Produk berhasil diperbarui.")
        return redirect("marketplace:seller_products")
    return render(request, "marketplace/product_form.html", {
        "form": form,
        "image_formset": image_formset,
        "page_title": "Edit Produk",
    })


@login_required
@require_POST
def product_delete(request, pk):
    product = get_object_or_404(Product, pk=pk, seller=request.user)
    if product.order_items.exists():
        product.is_available = False
        product.save(update_fields=["is_available", "updated_at"])
        messages.info(request, "Produk memiliki riwayat order, jadi ditandai tidak tersedia.")
    else:
        product.delete()
        messages.success(request, "Produk berhasil dihapus.")
    return redirect("marketplace:seller_products")


@login_required
@require_POST
def product_toggle_availability(request, pk):
    product = get_object_or_404(Product, pk=pk, seller=request.user)
    product.is_available = not product.is_available
    product.save(update_fields=["is_available", "updated_at"])
    return redirect("marketplace:seller_products")
