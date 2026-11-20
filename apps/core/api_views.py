from django.db import IntegrityError, transaction
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response

from .api_serializers import ReviewSerializer
from .models import Review, ReviewLike


class ReviewViewSet(viewsets.ModelViewSet):
    queryset = Review.objects.select_related("author").prefetch_related("likes")
    serializer_class = ReviewSerializer
    permission_classes = (permissions.IsAuthenticatedOrReadOnly,)

    def perform_create(self, serializer):
        try:
            with transaction.atomic():
                serializer.save(author=self.request.user, is_superuser_submission=self.request.user.is_superuser)
        except IntegrityError:
            raise ValidationError({"detail": "Pengguna sudah memiliki ulasan."})

    def perform_update(self, serializer):
        if serializer.instance.author_id != self.request.user.pk:
            raise PermissionDenied()
        serializer.save()

    def perform_destroy(self, instance):
        if instance.author_id != self.request.user.pk and not self.request.user.is_superuser:
            raise PermissionDenied()
        instance.delete()

    @action(detail=True, methods=["put", "delete"], permission_classes=[permissions.IsAuthenticated])
    def like(self, request, pk=None):
        review = self.get_object()
        if review.author_id == request.user.pk:
            raise PermissionDenied("Tidak dapat menyukai ulasan sendiri.")
        if request.method == "PUT":
            ReviewLike.objects.get_or_create(review=review, user=request.user)
        else:
            ReviewLike.objects.filter(review=review, user=request.user).delete()
        return Response({"liked": request.method == "PUT", "like_count": ReviewLike.objects.filter(review=review).count()}, status=status.HTTP_200_OK)
