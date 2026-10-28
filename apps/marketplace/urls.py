from django.urls import path

from . import views

app_name = "marketplace"

urlpatterns = [
    path("", views.show_shop, name="shop"),
    path("product/<int:pk>/", views.product_detail, name="product_detail"),
]
