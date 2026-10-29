from django.urls import path

from . import views

app_name = "marketplace"

urlpatterns = [
    path("", views.show_shop, name="shop"),
    path("product/<int:pk>/", views.product_detail, name="product_detail"),
    path("seller/products/", views.seller_products, name="seller_products"),
    path("seller/products/create/", views.product_create, name="product_create"),
    path("seller/products/<int:pk>/edit/", views.product_update, name="product_update"),
    path("seller/products/<int:pk>/delete/", views.product_delete, name="product_delete"),
    path("seller/products/<int:pk>/availability/", views.product_toggle_availability, name="product_toggle_availability"),
]
