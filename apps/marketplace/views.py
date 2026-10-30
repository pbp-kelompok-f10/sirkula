import json

from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET, require_http_methods

from .forms import SavedPlaceForm
from .models import Listing, PredefinedLocation, SavedPlace, Store
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_POST
from django.core.paginator import Paginator

from .models import Listing, PredefinedLocation, Product, Store
from .forms import ProductForm, ProductImageFormSet
from .services import (
    LocationServiceError,
    ResolvedCenter,
    geocode_address,
    geolocate_ip,
    get_client_ip,
    haversine_distance_km,
    reverse_geocode,
)


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


DEFAULT_PAGE_RADIUS_KM = 3


@require_GET
def discovery_map(request):
    locations = list(PredefinedLocation.objects.filter(is_active=True))
    selected_location = locations[0] if locations else None
    center_latitude = float(selected_location.latitude) if selected_location else -6.186486
    center_longitude = float(selected_location.longitude) if selected_location else 106.834091
    stores = []
    for store in Store.objects.filter(is_active=True):
        distance = haversine_distance_km(
            center_latitude, center_longitude, store.latitude, store.longitude
        )
        if distance <= DEFAULT_PAGE_RADIUS_KM:
            store.distance_km = round(distance, 1)
            stores.append(store)
    stores.sort(key=lambda store: store.distance_km)
    listings = []
    available_listings = Listing.objects.filter(
        is_available=True,
        store__is_active=True,
    ).select_related("store")
    for listing in available_listings:
        distance = haversine_distance_km(
            center_latitude, center_longitude, listing.latitude, listing.longitude
        )
        if distance <= DEFAULT_PAGE_RADIUS_KM:
            listing.distance_km = round(distance, 1)
            listings.append(listing)
    listings.sort(key=lambda listing: listing.distance_km)
    return render(request, "marketplace/discovery_map.html", {
        "locations": locations,
        "selected_location": selected_location,
        "nearby_stores": stores[:3],
        "nearby_listings": listings[:8],
        "radius_km": DEFAULT_PAGE_RADIUS_KM,
        "map_center": {"latitude": center_latitude, "longitude": center_longitude},
    })


def _map_error(message, *, status=400, field=None):
    payload = {"error": {"message": message}}
    if field:
        payload["error"]["field"] = field
    return JsonResponse(payload, status=status)


def _parse_json_body(request):
    try:
        payload = json.loads(request.body or b"{}")
    except (TypeError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("Request body must contain valid JSON.") from error
    if not isinstance(payload, dict):
        raise ValueError("Request body must be a JSON object.")
    return payload


def _form_error(form):
    return JsonResponse(
        {
            "error": {
                "message": "Please correct the invalid saved place fields.",
                "fields": form.errors.get_json_data(),
            }
        },
        status=400,
    )


def _serialize_saved_place(place):
    return {
        "id": place.pk,
        "name": place.name,
        "address_label": place.address_label,
        "notes": place.notes,
        "latitude": float(place.latitude),
        "longitude": float(place.longitude),
        "created_at": place.created_at.isoformat(),
        "updated_at": place.updated_at.isoformat(),
    }


def _saved_place_for_user(request, pk):
    return SavedPlace.objects.filter(pk=pk, user=request.user).first()


@require_http_methods(["GET", "POST"])
def saved_places(request):
    if not request.user.is_authenticated:
        return _map_error("Authentication is required to manage saved places.", status=401)

    if request.method == "GET":
        return JsonResponse(
            {
                "results": [
                    _serialize_saved_place(place)
                    for place in SavedPlace.objects.filter(user=request.user)
                ]
            }
        )

    try:
        payload = _parse_json_body(request)
    except ValueError as error:
        return _map_error(str(error))

    form = SavedPlaceForm(payload)
    if not form.is_valid():
        return _form_error(form)

    place = form.save(commit=False)
    place.user = request.user
    place.save()
    return JsonResponse({"result": _serialize_saved_place(place)}, status=201)


@require_http_methods(["GET", "PUT", "DELETE"])
def saved_place_detail(request, pk):
    if not request.user.is_authenticated:
        return _map_error("Authentication is required to manage saved places.", status=401)

    place = _saved_place_for_user(request, pk)
    if place is None:
        return _map_error("Saved place not found.", status=404)

    if request.method == "GET":
        return JsonResponse({"result": _serialize_saved_place(place)})

    if request.method == "DELETE":
        deleted_id = place.pk
        place.delete()
        return JsonResponse({"deleted_id": deleted_id})

    try:
        payload = _parse_json_body(request)
    except ValueError as error:
        return _map_error(str(error))

    form = SavedPlaceForm(payload, instance=place)
    if not form.is_valid():
        return _form_error(form)

    place = form.save()
    return JsonResponse({"result": _serialize_saved_place(place)})


def _parse_coordinate(value, *, field, minimum, maximum):
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{field} must be a number.")
    if not minimum <= parsed <= maximum:
        raise ValueError(f"{field} must be between {minimum} and {maximum}.")
    return parsed


def _resolve_center(request):
    latitude = request.GET.get("lat")
    longitude = request.GET.get("lon")
    location_slug = request.GET.get("location", "").strip()
    if latitude is not None or longitude is not None:
        if latitude is None or longitude is None:
            raise ValueError("lat and lon must be provided together.")
        return ResolvedCenter(
            _parse_coordinate(latitude, field="lat", minimum=-90, maximum=90),
            _parse_coordinate(longitude, field="lon", minimum=-180, maximum=180),
            request.GET.get("label", "Lokasi Anda")[:255],
            "coordinates",
        )
    if location_slug:
        try:
            location = PredefinedLocation.objects.get(slug=location_slug, is_active=True)
        except PredefinedLocation.DoesNotExist as error:
            raise ValueError("Unknown predefined location.") from error
        return ResolvedCenter(float(location.latitude), float(location.longitude), location.name, "predefined")
    return geolocate_ip(get_client_ip(request))


def _serialize_store(store, distance):
    return {
        "id": store.pk,
        "name": store.name,
        "slug": store.slug,
        "description": store.description,
        "address": store.address,
        "latitude": float(store.latitude),
        "longitude": float(store.longitude),
        "distance_km": round(distance, 2),
    }


def _serialize_listing(listing, distance):
    return {
        "id": listing.pk,
        "title": listing.title,
        "slug": listing.slug,
        "description": listing.description,
        "listing_type": listing.listing_type,
        "listing_type_label": listing.get_listing_type_display(),
        "price": str(listing.price) if listing.price is not None else None,
        "image_url": listing.image_url,
        "latitude": float(listing.latitude),
        "longitude": float(listing.longitude),
        "distance_km": round(distance, 2),
        "store": {"id": listing.store_id, "name": listing.store.name, "slug": listing.store.slug},
    }


@require_GET
def predefined_locations(request):
    query = request.GET.get("q", "").strip()
    locations = PredefinedLocation.objects.filter(is_active=True)
    if query:
        locations = locations.filter(Q(name__icontains=query) | Q(address_label__icontains=query))
    return JsonResponse({"results": [
        {
            "name": location.name,
            "slug": location.slug,
            "region_type": location.region_type,
            "address": location.address_label,
            "latitude": float(location.latitude),
            "longitude": float(location.longitude),
        }
        for location in locations
    ]})


@require_GET
def nearby_results(request):
    try:
        center = _resolve_center(request)
        radius = float(request.GET.get("radius", 3))
        if not 0.1 <= radius <= 100:
            return _map_error("radius must be between 0.1 and 100 kilometres.", field="radius")
    except ValueError as error:
        return _map_error(str(error))
    except LocationServiceError as error:
        return _map_error(str(error), status=503)
    query = request.GET.get("q", "").strip()
    stores = Store.objects.filter(is_active=True)
    listings = Listing.objects.filter(is_available=True, store__is_active=True).select_related("store")
    if query:
        stores = stores.filter(Q(name__icontains=query) | Q(description__icontains=query) | Q(address__icontains=query))
        listings = listings.filter(Q(title__icontains=query) | Q(description__icontains=query) | Q(store__name__icontains=query))
    nearby_stores = []
    for store in stores:
        distance = haversine_distance_km(center.latitude, center.longitude, store.latitude, store.longitude)
        if distance <= radius:
            nearby_stores.append((distance, store))
    nearby_listings = []
    for listing in listings:
        distance = haversine_distance_km(center.latitude, center.longitude, listing.latitude, listing.longitude)
        if distance <= radius:
            nearby_listings.append((distance, listing))
    nearby_stores.sort(key=lambda item: item[0])
    nearby_listings.sort(key=lambda item: item[0])
    return JsonResponse({
        "center": {
            "latitude": center.latitude,
            "longitude": center.longitude,
            "label": center.label,
            "source": center.source,
        },
        "radius_km": radius,
        "query": query,
        "stores": [_serialize_store(store, distance) for distance, store in nearby_stores],
        "listings": [_serialize_listing(listing, distance) for distance, listing in nearby_listings],
        "counts": {"stores": len(nearby_stores), "listings": len(nearby_listings)},
    })


@require_GET
def geocode(request):
    query = request.GET.get("q", "").strip()
    if len(query) < 3:
        return _map_error("q must contain at least 3 characters.", field="q")
    try:
        return JsonResponse({"results": geocode_address(query)})
    except LocationServiceError as error:
        return _map_error(str(error), status=503)


@require_GET
def reverse_geocode_view(request):
    try:
        latitude = _parse_coordinate(request.GET.get("lat"), field="lat", minimum=-90, maximum=90)
        longitude = _parse_coordinate(request.GET.get("lon"), field="lon", minimum=-180, maximum=180)
        return JsonResponse({"result": reverse_geocode(latitude, longitude)})
    except ValueError as error:
        return _map_error(str(error))
    except LocationServiceError as error:
        return _map_error(str(error), status=503)
