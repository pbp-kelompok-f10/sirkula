from django.db import IntegrityError, transaction
from django.http import HttpResponseForbidden
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from .forms import CategoryForm
from .models import Category

# Create your views here.
def wardrobe(request):
    if request.user.is_authenticated:
        categories = Category.objects.filter(owner=request.user)
        category_form = CategoryForm(owner=request.user)
    else:
        categories = Category.objects.none()
        category_form = None

    return render(request, "wardrobe.html", {
        "categories": categories,
        "category_form": category_form,
    })

@require_POST
def create_category(request):
    if not request.user.is_authenticated:
        return HttpResponseForbidden(
            "Silakan login untuk menambahkan kategori."
        )

    form = CategoryForm(request.POST, owner=request.user)

    if form.is_valid():
        category = form.save(commit=False)
        category.owner = request.user

        try:
            with transaction.atomic():
                category.save()
        except IntegrityError:
            duplicate_exists = Category.objects.filter(
                owner=request.user,
                name__iexact=category.name,
            ).exists()

            if not duplicate_exists:
                raise

            form.add_error(
                "name",
                "Kamu sudah memiliki kategori dengan nama ini.",
            )
        else:
            return redirect("wardrobe")

    return render(request, "wardrobe.html", {
        "categories": Category.objects.filter(owner=request.user),
        "category_form": form,
        "open_category_modal": True,
    }, status=400)