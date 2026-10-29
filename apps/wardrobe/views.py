import logging
from pathlib import Path

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.http import FileResponse, Http404, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST, require_safe
from django.views.decorators.vary import vary_on_cookie
from django.http import JsonResponse
from django.urls import reverse

from .forms import CategoryForm, WardrobeItemForm, WardrobeItemEditForm
from .models import (
    Category,
    WardrobeItem,
    WardrobeItemImage,
    WardrobePhotoCleanup,
)
from .cleanup import cleanup_pending_photos, queue_photo_cleanup


logger = logging.getLogger(__name__)

# Create your views here.
def _wardrobe_context(request):
    category_param = request.GET.get("category", "").strip()

    context = {
        "categories": Category.objects.none(),
        "clothes": WardrobeItem.objects.none(),
        "category_form": None,
        "item_form": None,
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

def _cleanup_failed_uploads(names):
    if not names:
        return
    try:
        cleanup_ids = queue_photo_cleanup(names)
        cleanup_pending_photos(cleanup_ids)
    except Exception:
        logger.exception(
            "Gagal mencatat antrean cleanup unggahan Wardrobe: %s",
            names,
        )


def _item_edit_error_response(form, status=400):
    return JsonResponse(
        {
            "ok": False,
            "errors": form.errors.get_json_data(),
        },
        status=status,
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
        _cleanup_failed_uploads(saved_names)
        form.add_error(
            "category",
            "Kategori tidak lagi tersedia. Pilih kategori milikmu.",
        )

    except ValidationError:
        _cleanup_failed_uploads(saved_names)
        logger.exception("Validasi penyimpanan pakaian gagal.")
        form.add_error(
            None,
            "Data pakaian tidak dapat disimpan. Periksa kembali isianmu.",
        )

    except Exception:
        _cleanup_failed_uploads(saved_names)
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

@transaction.non_atomic_requests
@never_cache
@vary_on_cookie
@require_POST
def update_item(request, item_id):
    if not request.user.is_authenticated:
        raise Http404("Pakaian tidak ditemukan.")

    image_field = WardrobeItemImage._meta.get_field("image")
    storage = image_field.storage

    saved_names = []
    form = None

    try:
        with transaction.atomic():
            item = get_object_or_404(
                WardrobeItem.objects.select_for_update(),
                pk=item_id,
                owner=request.user,
            )

            form = WardrobeItemEditForm(
                request.POST,
                request.FILES,
                owner=request.user,
                instance=item,
            )

            if not form.is_valid():
                return _item_edit_error_response(form)

            category = Category.objects.select_for_update().get(
                pk=form.cleaned_data["category"].pk,
                owner=request.user,
            )

            existing_photos = list(
                item.images.select_for_update().order_by(
                    "position",
                    "id",
                )
            )

            deleted_ids = set(
                form.cleaned_data["delete_photos"].values_list(
                    "pk",
                    flat=True,
                )
            )

            kept_photos = [
                photo
                for photo in existing_photos
                if photo.pk not in deleted_ids
            ]

            deleted_names = tuple(
                photo.image.name
                for photo in existing_photos
                if photo.pk in deleted_ids and photo.image.name
            )

            new_uploads = form.cleaned_data["photos"]
            final_count = len(kept_photos) + len(new_uploads)

            # Periksa kembali jumlah foto dalam transaksi.
            if not 1 <= final_count <= 5:
                form.add_error(
                    "photos",
                    "Jumlah akhir foto harus antara satu dan lima.",
                )
                return _item_edit_error_response(form)

            item = form.save(commit=False)
            item.category = category
            item.full_clean()
            item.save()

            new_photos = []

            for position, uploaded_file in enumerate(
                new_uploads,
                start=len(kept_photos) + 1,
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
                new_photos.append(photo)

            # Hapus baris database dahulu. File lama masih disimpan.
            if deleted_ids:
                item.images.filter(pk__in=deleted_ids).delete()

            # Urutkan foto lama yang dipertahankan sebelum
            # menambahkan foto baru agar posisi tidak bertabrakan.
            for position, photo in enumerate(
                kept_photos,
                start=1,
            ):
                if photo.position != position:
                    photo.position = position
                    photo.save(update_fields=["position"])

            for photo in new_photos:
                photo.full_clean()
                photo.save()

            # Antrean foto lama ikut di-commit bersama edit, sehingga
            # tetap tersedia jika callback gagal atau belum dijalankan.
            cleanup_ids = queue_photo_cleanup(deleted_names)
            transaction.on_commit(
                lambda ids=cleanup_ids: cleanup_pending_photos(ids),
                robust=True,
            )

    except Http404:
        _cleanup_failed_uploads(saved_names)
        raise

    except Category.DoesNotExist:
        _cleanup_failed_uploads(saved_names)

        form.add_error(
            "category",
            "Kategori tidak lagi tersedia. Pilih kategori milikmu.",
        )
        return _item_edit_error_response(form)

    except ValidationError:
        _cleanup_failed_uploads(saved_names)
        logger.exception(
            "Validasi edit pakaian gagal untuk item_id=%s.",
            item_id,
        )

        form.add_error(
            None,
            "Perubahan tidak dapat disimpan. "
            "Periksa kembali isianmu.",
        )
        return _item_edit_error_response(form)

    except Exception:
        _cleanup_failed_uploads(saved_names)
        logger.exception(
            "Edit pakaian gagal untuk item_id=%s, user_id=%s.",
            item_id,
            request.user.pk,
        )

        message = (
            "Perubahan gagal disimpan. Silakan coba lagi."
        )

        if form is not None:
            form.add_error(None, message)
            return _item_edit_error_response(form, status=500)

        return JsonResponse(
            {
                "ok": False,
                "errors": {
                    "__all__": [
                        {
                            "message": message,
                            "code": "",
                        }
                    ],
                },
            },
            status=500,
        )

    return JsonResponse({
        "ok": True,
        "item": {
            "id": item.pk,
        },
    })


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

@never_cache
@vary_on_cookie
@require_safe
def item_detail(request, item_id):
    if not request.user.is_authenticated:
        raise Http404("Pakaian tidak ditemukan.")

    item = get_object_or_404(
        WardrobeItem.objects.select_related(
            "category"
        ).prefetch_related("images"),
        pk=item_id,
        owner=request.user,
    )

    category = None

    if item.category is not None:
        category = {
            "id": item.category_id,
            "name": item.category.name,
        }

    photos = [
        {
            "id": photo.pk,
            "position": photo.position,
            "url": reverse(
                "wardrobe:item_photo",
                kwargs={"photo_id": photo.pk},
            ),
        }
        for photo in item.images.all()
    ]

    return JsonResponse({
        "item": {
            "id": item.pk,
            "name": item.name,
            "category": category,
            "photos": photos,
        },
    })


@transaction.non_atomic_requests
@never_cache
@vary_on_cookie
@require_POST
def delete_item(request, item_id):
    if not request.user.is_authenticated:
        raise Http404("Pakaian tidak ditemukan.")

    try:
        with transaction.atomic():
            item = get_object_or_404(
                WardrobeItem.objects.select_for_update(),
                pk=item_id,
                owner=request.user,
            )

            photos = list(
                item.images.select_for_update().all()
            )

            cleanup_ids = []

            for photo in photos:
                if not photo.image.name:
                    continue

                pending, _ = (
                    WardrobePhotoCleanup.objects.get_or_create(
                        file_name=photo.image.name,
                    )
                )
                cleanup_ids.append(pending.pk)

            # Baris foto ikut terhapus melalui CASCADE.
            # File storage belum disentuh pada tahap ini.
            item.delete()

            transaction.on_commit(
                lambda ids=tuple(cleanup_ids): (
                    cleanup_pending_photos(ids)
                ),
                robust=True,
            )

    except Http404:
        raise

    except Exception:
        logger.exception(
            "Penghapusan pakaian gagal untuk "
            "item_id=%s, user_id=%s.",
            item_id,
            request.user.pk,
        )

        return JsonResponse(
            {
                "ok": False,
                "errors": {
                    "__all__": [
                        {
                            "message": (
                                "Pakaian gagal dihapus. "
                                "Silakan coba lagi."
                            ),
                            "code": "delete_failed",
                        }
                    ],
                },
            },
            status=500,
        )

    return JsonResponse({
        "ok": True,
        "item": {
            "id": item_id,
        },
    })
