from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.http import require_POST
from django.shortcuts import get_object_or_404, redirect, render

from apps.marketplace.models import Product
from .models import BarterOffer

@login_required
def barter_chat(request, product_id):
    product = get_object_or_404(Product, pk=product_id, listing_type="BARTER")
    return render(request, "bartering/chat.html", {"product": product})


@login_required
def barter_mou(request, product_id):
    product = get_object_or_404(Product, pk=product_id, listing_type="BARTER")
    if request.method == "POST":
        if not request.POST.get("agree_mou"):
            return render(request, "bartering/mou.html", {"product": product, "error": "Setujui MoU terlebih dahulu."})
        request.session["barter_product_id"] = product.pk
        return redirect("bartering:payment", product_id=product.pk)
    return render(request, "bartering/mou.html", {"product": product})


@login_required
def barter_payment(request, product_id):
    product = get_object_or_404(Product, pk=product_id, listing_type="BARTER")
    if request.method == "POST":
        request.session.pop("barter_product_id", None)
        request.session["barter_success"] = True
        return redirect("bartering:success")
    return render(request, "bartering/payment.html", {"product": product})


@login_required
def barter_success(request):
    if not request.session.pop("barter_success", False):
        return redirect("core:home")
    return render(request, "bartering/success.html")


@login_required
def offer_create(request, product_id):
    requested_product = get_object_or_404(
        Product,
        pk=product_id,
        listing_type=Product.ListingType.BARTER,
        is_available=True,
    )
    offered_products = Product.objects.filter(
        seller=request.user,
        listing_type=Product.ListingType.BARTER,
        is_available=True,
    ).exclude(pk=requested_product.pk)
    if request.method == "POST":
        offered_product = get_object_or_404(
            offered_products,
            pk=request.POST.get("offered_product"),
        )
        BarterOffer.objects.create(
            proposer=request.user,
            recipient=requested_product.seller,
            requested_product=requested_product,
            offered_product=offered_product,
            message=request.POST.get("message", "").strip(),
        )
        return redirect("bartering:outgoing")
    return render(request, "bartering/offer_form.html", {
        "requested_product": requested_product,
        "offered_products": offered_products,
    })


@login_required
def incoming_offers(request):
    offers = BarterOffer.objects.filter(
        recipient=request.user,
    ).select_related("proposer", "requested_product", "offered_product")
    return render(request, "bartering/offer_list.html", {
        "offers": offers,
        "page_title": "Tawaran Barter Masuk",
        "incoming": True,
    })


@login_required
def outgoing_offers(request):
    offers = BarterOffer.objects.filter(
        proposer=request.user,
    ).select_related("recipient", "requested_product", "offered_product")
    return render(request, "bartering/offer_list.html", {
        "offers": offers,
        "page_title": "Tawaran Barter Keluar",
        "incoming": False,
    })


@login_required
def update_offer_status(request, offer_id, status):
    if request.method != "POST":
        return redirect("bartering:incoming")
    offer = get_object_or_404(BarterOffer, pk=offer_id)
    if status == BarterOffer.Status.ACCEPTED or status == BarterOffer.Status.REJECTED:
        if offer.recipient_id != request.user.id or offer.status != BarterOffer.Status.PENDING:
            return redirect("bartering:incoming")
    elif status == BarterOffer.Status.CANCELLED:
        if offer.proposer_id != request.user.id or offer.status != BarterOffer.Status.PENDING:
            return redirect("bartering:outgoing")
    else:
        return redirect("bartering:incoming")
    offer.status = status
    offer.save(update_fields=["status", "updated_at"])
    return redirect("bartering:incoming" if status != BarterOffer.Status.CANCELLED else "bartering:outgoing")


@login_required
@require_POST
def update_shipping(request, offer_id):
    offer = get_object_or_404(BarterOffer, pk=offer_id)
    if request.user.id not in {offer.proposer_id, offer.recipient_id}:
        messages.error(request, "Kamu bukan pihak dalam barter ini.")
        return redirect("bartering:outgoing")
    if offer.status not in {BarterOffer.Status.ACCEPTED, BarterOffer.Status.SHIPPING}:
        messages.error(request, "Barter belum siap dikirim.")
        return redirect("bartering:outgoing")

    tracking_number = request.POST.get("tracking_number", "").strip()
    if not tracking_number:
        messages.error(request, "Nomor resi wajib diisi.")
        return redirect("bartering:outgoing")
    if request.user.id == offer.proposer_id:
        offer.proposer_tracking_number = tracking_number
    else:
        offer.recipient_tracking_number = tracking_number
    if offer.proposer_tracking_number and offer.recipient_tracking_number:
        offer.status = BarterOffer.Status.SHIPPING
    offer.save(update_fields=[
        "proposer_tracking_number",
        "recipient_tracking_number",
        "status",
        "updated_at",
    ])
    return redirect("bartering:outgoing" if request.user.id == offer.proposer_id else "bartering:incoming")


@login_required
@require_POST
def confirm_received(request, offer_id):
    offer = get_object_or_404(BarterOffer, pk=offer_id)
    if request.user.id not in {offer.proposer_id, offer.recipient_id}:
        messages.error(request, "Kamu bukan pihak dalam barter ini.")
        return redirect("bartering:outgoing")
    if offer.status != BarterOffer.Status.SHIPPING:
        messages.error(request, "Barter belum masuk tahap pengiriman.")
        return redirect("bartering:outgoing")
    if request.user.id == offer.proposer_id:
        offer.proposer_received = True
    else:
        offer.recipient_received = True
    if offer.proposer_received and offer.recipient_received:
        offer.status = BarterOffer.Status.COMPLETED
    offer.save(update_fields=["proposer_received", "recipient_received", "status", "updated_at"])
    return redirect("bartering:outgoing" if request.user.id == offer.proposer_id else "bartering:incoming")
