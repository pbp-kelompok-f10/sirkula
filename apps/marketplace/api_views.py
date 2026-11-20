from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework import generics, permissions, serializers, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from .api_serializers import (
    PredefinedLocationSerializer, ProductImageSerializer, ProductSerializer,
    SavedPlaceSerializer,
)
from .models import Listing, PredefinedLocation, Product, ProductImage, SavedPlace, Store
from .services import (
    LocationServiceError, ResolvedCenter, geocode_address, geolocate_ip,
    get_client_ip, haversine_distance_km, reverse_geocode,
)
from .views import _serialize_listing, _serialize_store


class CatalogView(generics.ListAPIView):
    permission_classes = (permissions.AllowAny,)
    serializer_class = ProductSerializer

    def get_queryset(self):
        products = Product.objects.filter(is_available=True).select_related("seller").prefetch_related("gallery")
        params = self.request.query_params
        query = params.get("q", "").strip()
        size = params.get("size", "").strip()
        location = params.get("location", "").strip()
        if query:
            products = products.filter(name__icontains=query)
        if size:
            products = products.filter(size__iexact=size)
        if location:
            products = products.filter(location__icontains=location)
        for field, lookup in (("min_price", "price__gte"), ("max_price", "price__lte")):
            value = params.get(field, "").strip()
            if value:
                if not value.isascii() or not value.isdigit():
                    raise serializers.ValidationError({field: "Enter a non-negative integer."})
                products = products.filter(**{lookup: value})
        return products


class ProductDetailView(generics.RetrieveAPIView):
    permission_classes = (permissions.AllowAny,)
    serializer_class = ProductSerializer
    queryset = Product.objects.select_related("seller").prefetch_related("gallery")


class MyProductsView(generics.ListCreateAPIView):
    permission_classes = (permissions.IsAuthenticated,)
    serializer_class = ProductSerializer

    def get_queryset(self):
        return Product.objects.filter(seller=self.request.user).prefetch_related("gallery")

    def perform_create(self, serializer):
        serializer.save(seller=self.request.user)


class MyProductDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = (permissions.IsAuthenticated,)
    serializer_class = ProductSerializer

    def get_queryset(self):
        return Product.objects.filter(seller=self.request.user).prefetch_related("gallery")

    def perform_destroy(self, instance):
        if instance.order_items.exists():
            instance.is_available = False
            instance.save(update_fields=["is_available", "updated_at"])
        else:
            instance.delete()


class GalleryListView(generics.ListCreateAPIView):
    permission_classes = (permissions.IsAuthenticated,)
    serializer_class = ProductImageSerializer

    def product(self):
        return get_object_or_404(Product, pk=self.kwargs["product_pk"], seller=self.request.user)

    def get_queryset(self):
        return self.product().gallery.all()

    def perform_create(self, serializer):
        serializer.save(product=self.product())


class GalleryDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = (permissions.IsAuthenticated,)
    serializer_class = ProductImageSerializer

    def get_queryset(self):
        return ProductImage.objects.filter(product_id=self.kwargs["product_pk"], product__seller=self.request.user)


class SavedPlacesView(generics.ListCreateAPIView):
    permission_classes = (permissions.IsAuthenticated,)
    serializer_class = SavedPlaceSerializer

    def get_queryset(self):
        return SavedPlace.objects.filter(user=self.request.user)

    @transaction.atomic
    def perform_create(self, serializer):
        user = get_user_model().objects.select_for_update().get(pk=self.request.user.pk)
        if SavedPlace.objects.filter(user=user).count() >= 3:
            raise serializers.ValidationError({"detail": "A maximum of 3 places can be saved."})
        serializer.save(user=user)


class SavedPlaceDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = (permissions.IsAuthenticated,)
    serializer_class = SavedPlaceSerializer

    def get_queryset(self):
        return SavedPlace.objects.filter(user=self.request.user)


class LocationListView(generics.ListAPIView):
    permission_classes = (permissions.AllowAny,)
    serializer_class = PredefinedLocationSerializer

    def get_queryset(self):
        locations = PredefinedLocation.objects.filter(is_active=True)
        query = self.request.query_params.get("q", "").strip()
        if query:
            locations = locations.filter(Q(name__icontains=query) | Q(address_label__icontains=query))
        return locations


def coordinate(value, field, minimum, maximum):
    try:
        result = float(value)
    except (TypeError, ValueError):
        raise serializers.ValidationError({field: "Enter a valid number."})
    if not minimum <= result <= maximum:
        raise serializers.ValidationError({field: f"Must be between {minimum} and {maximum}."})
    return result


def resolve_center(request):
    params = request.query_params
    lat, lon = params.get("lat"), params.get("lon")
    if lat is not None or lon is not None:
        if lat is None or lon is None:
            raise serializers.ValidationError({"detail": "lat and lon must be provided together."})
        return ResolvedCenter(coordinate(lat, "lat", -90, 90), coordinate(lon, "lon", -180, 180), params.get("label", "Lokasi Anda")[:255], "coordinates")
    slug = params.get("location", "").strip()
    if slug:
        location = PredefinedLocation.objects.filter(slug=slug, is_active=True).first()
        if location is None:
            raise serializers.ValidationError({"location": "Unknown predefined location."})
        return ResolvedCenter(float(location.latitude), float(location.longitude), location.name, "predefined")
    return geolocate_ip(get_client_ip(request))


@api_view(["GET"])
@permission_classes([permissions.AllowAny])
def nearby(request):
    radius = coordinate(request.query_params.get("radius", 3), "radius", 0.1, 100)
    try:
        center = resolve_center(request)
    except LocationServiceError as error:
        return Response({"detail": str(error)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
    query = request.query_params.get("q", "").strip()
    stores = Store.objects.filter(is_active=True)
    listings = Listing.objects.filter(is_available=True, store__is_active=True).select_related("store")
    if query:
        stores = stores.filter(Q(name__icontains=query) | Q(description__icontains=query) | Q(address__icontains=query))
        listings = listings.filter(Q(title__icontains=query) | Q(description__icontains=query) | Q(store__name__icontains=query))
    nearby_stores = []
    nearby_listings = []
    for objects, results in ((stores, nearby_stores), (listings, nearby_listings)):
        for obj in objects:
            distance = haversine_distance_km(center.latitude, center.longitude, obj.latitude, obj.longitude)
            if distance <= radius:
                results.append((distance, obj))
        results.sort(key=lambda item: item[0])
    return Response({
        "center": {"latitude": center.latitude, "longitude": center.longitude, "label": center.label, "source": center.source},
        "radius_km": radius, "query": query,
        "stores": [_serialize_store(obj, distance) for distance, obj in nearby_stores],
        "listings": [_serialize_listing(obj, distance) for distance, obj in nearby_listings],
        "counts": {"stores": len(nearby_stores), "listings": len(nearby_listings)},
    })


@api_view(["GET"])
@permission_classes([permissions.AllowAny])
def geocode(request):
    query = request.query_params.get("q", "").strip()
    if len(query) < 3:
        raise serializers.ValidationError({"q": "Must contain at least 3 characters."})
    try:
        return Response({"results": geocode_address(query)})
    except LocationServiceError as error:
        return Response({"detail": str(error)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)


@api_view(["GET"])
@permission_classes([permissions.AllowAny])
def reverse_geocode_view(request):
    latitude = coordinate(request.query_params.get("lat"), "lat", -90, 90)
    longitude = coordinate(request.query_params.get("lon"), "lon", -180, 180)
    try:
        return Response({"result": reverse_geocode(latitude, longitude)})
    except LocationServiceError as error:
        return Response({"detail": str(error)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
