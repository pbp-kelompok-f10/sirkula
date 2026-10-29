from django.shortcuts import get_object_or_404, redirect, render

from apps.marketplace.models import Product

def barter_chat(request, product_id):
    product = get_object_or_404(Product, pk=product_id, listing_type="BARTER")
    return render(request, "bartering/chat.html", {"product": product})


def barter_mou(request, product_id):
    product = get_object_or_404(Product, pk=product_id, listing_type="BARTER")
    if request.method == "POST":
        if not request.POST.get("agree_mou"):
            return render(request, "bartering/mou.html", {"product": product, "error": "Setujui MoU terlebih dahulu."})
        request.session["barter_product_id"] = product.pk
        return redirect("bartering:payment", product_id=product.pk)
    return render(request, "bartering/mou.html", {"product": product})


def barter_payment(request, product_id):
    product = get_object_or_404(Product, pk=product_id, listing_type="BARTER")
    if request.method == "POST":
        request.session.pop("barter_product_id", None)
        request.session["barter_success"] = True
        return redirect("bartering:success")
    return render(request, "bartering/payment.html", {"product": product})


def barter_success(request):
    if not request.session.pop("barter_success", False):
        return redirect("core:home")
    return render(request, "bartering/success.html")
