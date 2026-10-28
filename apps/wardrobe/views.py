import logging
from pathlib import Path

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.http import FileResponse, Http404, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST, require_safe
from django.views.decorators.vary import vary_on_cookie

from .forms import CategoryForm, WardrobeItemForm
from .models import Category, WardrobeItem, WardrobeItemImage


logger = logging.getLogger(__name__)

# Create your views here.
def _wardrobe_context(request):
    search_query = request.GET.get("q", "").strip()
    category_param = request.GET.get("category", "").strip()

    context = {
        "categories": Category.objects.none(),
        "clothes": WardrobeItem.objects.none(),
        "category_form": None,
        "item_form": None,
        "search_query": search_query,
        "active_category_id": None,
    }

    if not request.user.is_authenticated:
        if category_param:
            raise Http404("Kategori tidak ditemukan.")

        return context

    categories = Category.objects.filter(owner=request.user)

    clothes = (
        WardrobeItem.objects.filter(owner=request.user)
        .select_related("category")
        .prefetch_related("images")
    )

    if search_query:
        clothes = clothes.filter(name__icontains=search_query)

    if category_param:
        try:
            category_id = int(category_param)
        except ValueError:
            raise Http404("Kategori tidak ditemukan.") from None

        if not 1 <= category_id <= 9_223_372_036_854_775_807:
            raise Http404("Kategori tidak ditemukan.")

        category = get_object_or_404(
            categories,
            pk=category_id,
        )

        clothes = clothes.filter(category=category)
        context["active_category_id"] = category.pk

    context.update({
        "categories": categories,
        "clothes": clothes,
        "category_form": CategoryForm(owner=request.user),
        "item_form": WardrobeItemForm(owner=request.user),
    })

    return context

def wardrobe(request):
    return render(
        request,
        "wardrobe/index.html",
        _wardrobe_context(request),
    )

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
            return redirect("wardrobe:index")

    context = _wardrobe_context(request)
    context.update({
        "category_form": form,
        "open_category_modal": True,
    })

    return render(
        request,
        "wardrobe/index.html",
        context,
        status=400,
    )

def _cleanup_uploaded_photos(storage, names):
    for name in reversed(names):
        try:
            storage.delete(name)
        except Exception:
            logger.exception(
                "Gagal membersihkan file foto Wardrobe: %s",
                name,
            )


@transaction.non_atomic_requests
@require_POST
def create_item(request):
    if not request.user.is_authenticated:
        return HttpResponseForbidden(
            "Silakan login untuk menambahkan pakaian."
        )

    form = WardrobeItemForm(
        request.POST,
        request.FILES,
        owner=request.user,
    )

    if not form.is_valid():
        context = _wardrobe_context(request)
        context.update({
            "item_form": form,
            "open_item_modal": True,
        })

        return render(
            request,
            "wardrobe/index.html",
            context,
            status=400,
        )

    image_field = WardrobeItemImage._meta.get_field("image")
    storage = image_field.storage
    saved_names = []
    response_status = 400

    try:
        with transaction.atomic():
            category = Category.objects.select_for_update().get(
                pk=form.cleaned_data["category"].pk,
                owner=request.user,
            )

            item = form.save(commit=False)
            item.owner = request.user
            item.category = category
            item.full_clean()
            item.save()

            for position, uploaded_file in enumerate(
                form.cleaned_data["photos"],
                start=1,
            ):
                photo = WardrobeItemImage(
                    item=item,
                    position=position,
                )

                uploaded_file.seek(0)

                filename = image_field.generate_filename(
                    photo,
                    uploaded_file.name,
                )

                saved_name = storage.save(
                    filename,
                    uploaded_file,
                    max_length=image_field.max_length,
                )

                saved_names.append(saved_name)

                photo.image = saved_name
                photo.full_clean()
                photo.save()

    except Category.DoesNotExist:
        _cleanup_uploaded_photos(storage, saved_names)
        form.add_error(
            "category",
            "Kategori tidak lagi tersedia. Pilih kategori milikmu.",
        )

    except ValidationError:
        _cleanup_uploaded_photos(storage, saved_names)
        logger.exception("Validasi penyimpanan pakaian gagal.")
        form.add_error(
            None,
            "Data pakaian tidak dapat disimpan. Periksa kembali isianmu.",
        )

    except Exception:
        _cleanup_uploaded_photos(storage, saved_names)
        logger.exception(
            "Penyimpanan pakaian gagal untuk user_id=%s.",
            request.user.pk,
        )
        form.add_error(
            None,
            "Pakaian gagal disimpan. Silakan coba lagi.",
        )
        response_status = 500

    else:
        return redirect("wardrobe:index")

    context = _wardrobe_context(request)
    context.update({
        "item_form": form,
        "open_item_modal": True,
    })

    return render(
        request,
        "wardrobe/index.html",
        context,
        status=response_status,
    )


@never_cache
@vary_on_cookie
@require_safe
def item_photo(request, photo_id):
    if not request.user.is_authenticated:
        raise Http404("Foto tidak ditemukan.")

    photo = get_object_or_404(
        WardrobeItemImage.objects.select_related("item"),
        pk=photo_id,
        item__owner=request.user,
    )

    if not photo.image:
        raise Http404("Foto tidak ditemukan.")

    extension = Path(photo.image.name).suffix.lower()
    content_type = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
    }.get(extension)
    if content_type is None:
        raise Http404("Foto tidak ditemukan.")

    try:
        image_file = photo.image.open("rb")
    except FileNotFoundError:
        raise Http404("Foto tidak ditemukan.") from None

    response = FileResponse(
        image_file,
        content_type=content_type,
        as_attachment=False,
        filename=f"wardrobe-photo-{photo.pk}{extension}",
    )
    response["X-Content-Type-Options"] = "nosniff"
    response["Cross-Origin-Resource-Policy"] = "same-origin"
    return response
