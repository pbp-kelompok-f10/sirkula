from django.urls import path
from . import views

app_name = "marketplace"

urlpatterns = [
    path("map/", views.discovery_map, name="discovery_map"),
    path("api/locations/", views.predefined_locations, name="api_locations"),
    path("api/nearby/", views.nearby_results, name="api_nearby"),
    path("api/geocode/", views.geocode, name="api_geocode"),
    path("api/reverse-geocode/", views.reverse_geocode_view, name="api_reverse_geocode"),
]
