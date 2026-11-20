from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from rest_framework import generics, permissions, serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .api_serializers import CategorySerializer, ItemSerializer
from .cleanup import cleanup_pending_photos, queue_photo_cleanup
from .models import Category, WardrobeItem
from .views import _apply_draft_photos, _cleanup_failed_uploads, item_photo


@method_decorator(never_cache, name="dispatch")
class CategoryList(generics.ListCreateAPIView):
    serializer_class = CategorySerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Category.objects.filter(owner=self.request.user)

    def perform_create(self, serializer):
        try:
            with transaction.atomic():
                serializer.save(owner=self.request.user)
        except IntegrityError:
            raise serializers.ValidationError({"name": "Nama kategori sudah digunakan."})


@method_decorator(never_cache, name="dispatch")
class CategoryDetail(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = CategorySerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Category.objects.filter(owner=self.request.user)

    def perform_update(self, serializer):
        try:
            with transaction.atomic():
                serializer.save()
        except IntegrityError:
            raise serializers.ValidationError({"name": "Nama kategori sudah digunakan."})


@method_decorator(never_cache, name="dispatch")
class ItemList(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        items = WardrobeItem.objects.filter(owner=request.user).select_related("category").prefetch_related("images")
        return Response(ItemSerializer(items, many=True, context={"request": request}).data)

    def post(self, request):
        return save_item(request)


@method_decorator(never_cache, name="dispatch")
class ItemDetail(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, pk):
        item = get_object_or_404(WardrobeItem.objects.select_related("category").prefetch_related("images"), pk=pk, owner=request.user)
        return Response(ItemSerializer(item, context={"request": request}).data)

    def put(self, request, pk):
        return save_item(request, pk=pk)

    def patch(self, request, pk):
        return save_item(request, pk=pk, partial=True)

    def delete(self, request, pk):
        with transaction.atomic():
            item = get_object_or_404(WardrobeItem.objects.select_for_update(), pk=pk, owner=request.user)
            ids = queue_photo_cleanup(item.images.values_list("image", flat=True))
            item.delete()
            transaction.on_commit(lambda: cleanup_pending_photos(ids), robust=True)
        return Response(status=status.HTTP_204_NO_CONTENT)


def save_item(request, pk=None, partial=False):
    saved_names = []
    try:
        with transaction.atomic():
            get_user_model().objects.select_for_update().get(pk=request.user.pk)
            item = get_object_or_404(WardrobeItem.objects.select_for_update(), pk=pk, owner=request.user) if pk is not None else None
            serializer = ItemSerializer(item, data=request.data, partial=partial, context={"request": request})
            serializer.is_valid(raise_exception=True)
            data = dict(serializer.validated_data)
            photos = data.pop("photos", [])
            deleted = data.pop("delete_photos", [])
            category = data.get("category", item.category if item is not None else None)
            if category is not None:
                category = get_object_or_404(Category.objects.select_for_update(), pk=category.pk, owner=request.user)
                if "category" in data:
                    data["category"] = category
            if item is None:
                item = WardrobeItem(owner=request.user, **data)
            else:
                for key, value in data.items():
                    setattr(item, key, value)
            item.save()
            cleanup_ids = _apply_draft_photos(item, {"photos": photos, "delete_photos": item.images.filter(pk__in=deleted)}, saved_names)
            transaction.on_commit(lambda: cleanup_pending_photos(cleanup_ids), robust=True)
    except IntegrityError:
        _cleanup_failed_uploads(saved_names)
        raise serializers.ValidationError({"status": "Hanya satu draft diperbolehkan."})
    except Exception:
        _cleanup_failed_uploads(saved_names)
        raise
    return Response(ItemSerializer(item, context={"request": request}).data, status=status.HTTP_201_CREATED if pk is None else status.HTTP_200_OK)


@method_decorator(never_cache, name="dispatch")
class PhotoDetail(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, photo_id):
        return item_photo(request._request, photo_id)
