from django.urls import path

from . import api_views

app_name = "marketplace_api"

urlpatterns = [
    path("products/", api_views.CatalogView.as_view(), name="catalog"),
    path("products/<int:pk>/", api_views.ProductDetailView.as_view(), name="product-detail"),
    path("my/products/", api_views.MyProductsView.as_view(), name="my-products"),
    path("my/products/<int:pk>/", api_views.MyProductDetailView.as_view(), name="my-product-detail"),
    path("my/products/<int:product_pk>/images/", api_views.GalleryListView.as_view(), name="product-images"),
    path("my/products/<int:product_pk>/images/<int:pk>/", api_views.GalleryDetailView.as_view(), name="product-image-detail"),
    path("map/locations/", api_views.LocationListView.as_view(), name="locations"),
    path("map/nearby/", api_views.nearby, name="nearby"),
    path("map/geocode/", api_views.geocode, name="geocode"),
    path("map/reverse-geocode/", api_views.reverse_geocode_view, name="reverse-geocode"),
    path("map/saved-places/", api_views.SavedPlacesView.as_view(), name="saved-places"),
    path("map/saved-places/<int:pk>/", api_views.SavedPlaceDetailView.as_view(), name="saved-place-detail"),
]
