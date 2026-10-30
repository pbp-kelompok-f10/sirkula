from django.urls import path

from . import views

app_name = "marketplace"

urlpatterns = [
    path("map/", views.discovery_map, name="discovery_map"),
    path("api/saved-places/", views.saved_places, name="api_saved_places"),
    path(
        "api/saved-places/<int:pk>/",
        views.saved_place_detail,
        name="api_saved_place_detail",
    ),
    path("api/locations/", views.predefined_locations, name="api_locations"),
    path("api/nearby/", views.nearby_results, name="api_nearby"),
    path("api/geocode/", views.geocode, name="api_geocode"),
    path("api/reverse-geocode/", views.reverse_geocode_view, name="api_reverse_geocode"),
    path("", views.show_shop, name="shop"),
    path("product/<int:pk>/", views.product_detail, name="product_detail"),
    path("seller/products/", views.seller_products, name="seller_products"),
    path("seller/products/create/", views.product_create, name="product_create"),
    path("seller/products/<int:pk>/edit/", views.product_update, name="product_update"),
    path("seller/products/<int:pk>/delete/", views.product_delete, name="product_delete"),
    path("seller/products/<int:pk>/availability/", views.product_toggle_availability, name="product_toggle_availability"),
]
