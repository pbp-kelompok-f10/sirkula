from urllib.parse import urlencode

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db import IntegrityError, transaction
from django.db.models import Count, Exists, OuterRef
from django.http import HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render, resolve_url
from django.urls import reverse
from django.views.decorators.http import require_http_methods, require_POST

from .forms import ReviewForm
from .models import Review, ReviewLike


def home(request):
    reviews = Review.objects.select_related("author").annotate(like_count=Count("likes")).order_by("-created_at", "-pk")
    own_review = None
    if request.user.is_authenticated:
        reviews = reviews.annotate(
            liked_by_me=Exists(ReviewLike.objects.filter(review_id=OuterRef("pk"), user=request.user))
        )
        own_review = Review.objects.filter(author=request.user).first()
    page = Paginator(reviews, 20).get_page(request.GET.get("reviews_page"))
    return render(request, "core/home.html", {
        "reviews_page": page,
        "own_review": own_review,
        "review_login_url": resolve_url(settings.LOGIN_URL),
    })


def show_components(request):
    return render(request, "components.html")


def _reviews_redirect():
    return redirect(reverse("core:home") + "#reviews")


@login_required
@require_http_methods(["GET", "POST"])
def review_create(request):
    existing = Review.objects.filter(author=request.user).first()
    if existing and not request.user.is_superuser:
        messages.info(request, "Kamu sudah punya ulasan. Kamu bisa memperbaruinya di sini.")
        return redirect("core:review_update", pk=existing.pk)
    form = ReviewForm(request.POST if request.method == "POST" else None)
    if request.method == "POST" and form.is_valid():
        review = form.save(commit=False)
        review.author = request.user
        review.is_superuser_submission = request.user.is_superuser
        try:
            with transaction.atomic():
                review.save()
        except IntegrityError:
            if request.user.is_superuser:
                raise
            # A concurrent submission may already have created this user's review.
            existing = Review.objects.filter(author=request.user).first()
            if existing is None:
                raise
            return redirect("core:review_update", pk=existing.pk)
        messages.success(request, "Terima kasih! Ulasanmu sudah diterbitkan.")
        return _reviews_redirect()
    return render(request, "core/reviews/form.html", {"form": form, "editing": False})


@login_required
@require_http_methods(["GET", "POST"])
def review_update(request, pk):
    review = get_object_or_404(Review, pk=pk)
    if review.author_id != request.user.pk:
        raise PermissionDenied
    form = ReviewForm(request.POST if request.method == "POST" else None, instance=review)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Ulasanmu berhasil diperbarui.")
        return _reviews_redirect()
    return render(request, "core/reviews/form.html", {"form": form, "editing": True})


@login_required
@require_http_methods(["GET", "POST"])
def review_delete(request, pk):
    review = get_object_or_404(Review, pk=pk)
    if review.author_id != request.user.pk and not request.user.is_superuser:
        raise PermissionDenied
    if request.method == "POST":
        review.delete()
        messages.success(request, "Ulasan berhasil dihapus.")
        return _reviews_redirect()
    return render(request, "core/reviews/confirm_delete.html", {"review": review})


@login_required
@require_POST
def review_like(request, pk):
    review = get_object_or_404(Review, pk=pk)
    if review.author_id == request.user.pk:
        raise PermissionDenied
    action = request.POST.get("action")
    if action == "like":
        ReviewLike.objects.get_or_create(review=review, user=request.user)
    elif action == "unlike":
        ReviewLike.objects.filter(review=review, user=request.user).delete()
    else:
        return HttpResponseBadRequest("Aksi tidak valid.")
    try:
        page = max(1, int(request.POST.get("page", "1")))
    except (ValueError, TypeError):
        page = 1
    return redirect(reverse("core:home") + "?" + urlencode({"reviews_page": page}) + "#reviews")
