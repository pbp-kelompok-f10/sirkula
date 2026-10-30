import ipaddress
import math
from dataclasses import dataclass

import httpx
from django.conf import settings
from django.core.cache import cache


DEFAULT_CENTER = (-6.186486, 106.834091)
EARTH_RADIUS_KM = 6371.0088


class LocationServiceError(Exception):
    """Raised when an external location provider cannot resolve a location."""


@dataclass(frozen=True)
class ResolvedCenter:
    latitude: float
    longitude: float
    label: str
    source: str


def haversine_distance_km(latitude_a, longitude_a, latitude_b, longitude_b):
    # Mengembalikan jarak dengan rumus haversine (gua nyontek gugel jir)
    lat_a, lon_a, lat_b, lon_b = map(
        math.radians,
        (float(latitude_a), float(longitude_a), float(latitude_b), float(longitude_b)),
    )
    delta_latitude = lat_b - lat_a
    delta_longitude = lon_b - lon_a
    haversine = (
        math.sin(delta_latitude / 2) ** 2
        + math.cos(lat_a) * math.cos(lat_b) * math.sin(delta_longitude / 2) ** 2
    )
    return EARTH_RADIUS_KM * 2 * math.atan2(math.sqrt(haversine), math.sqrt(1 - haversine))


def get_client_ip(request):
    forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR", "")
    return forwarded_for.split(",", 1)[0].strip() or request.META.get("REMOTE_ADDR", "")


def _request_json(url, *, params=None):
    headers = {
        "User-Agent": settings.LOCATION_USER_AGENT,
        "Accept": "application/json",
    }
    try:
        response = httpx.get(
            url,
            params=params,
            headers=headers,
            timeout=settings.LOCATION_REQUEST_TIMEOUT,
            follow_redirects=True,
        )
        response.raise_for_status()
        return response.json()
    except (httpx.HTTPError, ValueError, TypeError) as error:
        raise LocationServiceError("Location provider is currently unavailable.") from error


def geocode_address(query, *, limit=5):
    cache_key = f"marketplace:geocode:{query.casefold()}:{limit}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    payload = _request_json(
        settings.NOMINATIM_BASE_URL.rstrip("/") + "/search",
        params={
            "q": query,
            "format": "jsonv2",
            "addressdetails": 1,
            "countrycodes": "id",
            "limit": limit,
        },
    )
    results = [
        {
            "latitude": float(item["lat"]),
            "longitude": float(item["lon"]),
            "label": item.get("display_name", query),
        }
        for item in payload
        if "lat" in item and "lon" in item
    ]
    cache.set(cache_key, results, settings.LOCATION_CACHE_SECONDS)
    return results


def reverse_geocode(latitude, longitude):
    cache_key = f"marketplace:reverse:{latitude:.5f}:{longitude:.5f}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    payload = _request_json(
        settings.NOMINATIM_BASE_URL.rstrip("/") + "/reverse",
        params={
            "lat": latitude,
            "lon": longitude,
            "format": "jsonv2",
            "addressdetails": 1,
        },
    )
    result = {
        "latitude": float(payload.get("lat", latitude)),
        "longitude": float(payload.get("lon", longitude)),
        "label": payload.get("display_name", "Lokasi dipilih"),
        "address": payload.get("address", {}),
    }
    cache.set(cache_key, result, settings.LOCATION_CACHE_SECONDS)
    return result


# attempt buat dapetin geolokasi berdasarkan IP, nanti akan mengarah ke lokasi ISP
# kecuali dia pakai VPN, ini pendekatan yang gak begitu baik tapi mungkin cukup
# representatif, cuman dipakai kalau user gak izinin lokasi aja sih
def geolocate_ip(ip_address):
    # defaultnya ke jakpus
    fallback = ResolvedCenter(*settings.MARKETPLACE_DEFAULT_CENTER, "Jakarta Pusat", "fallback")
    try:
        parsed_ip = ipaddress.ip_address(ip_address)
    except ValueError:
        return fallback
    if parsed_ip.is_private or parsed_ip.is_loopback or parsed_ip.is_reserved:
        return fallback

    cache_key = f"marketplace:ip:{parsed_ip.compressed}"
    cached = cache.get(cache_key)
    if cached is not None:
        return ResolvedCenter(**cached)

    payload = _request_json(
        settings.IP_GEOLOCATION_URL.format(ip=parsed_ip.compressed),
    )
    try:
        result = ResolvedCenter(
            latitude=float(payload["latitude"]),
            longitude=float(payload["longitude"]),
            label=payload.get("city") or payload.get("region") or "Lokasi berdasarkan IP",
            source="ip",
        )
    except (KeyError, TypeError, ValueError) as error:
        raise LocationServiceError("IP location provider returned invalid data.") from error
    cache.set(cache_key, result.__dict__, settings.LOCATION_CACHE_SECONDS)
    return result
