from django.urls import path

from . import views

app_name = "transactions"

urlpatterns = [
    path("cart/", views.cart_detail, name="cart"),
    path("cart/add/<int:product_id>/", views.cart_add, name="cart_add"),
    path("cart/remove/<int:product_id>/", views.cart_remove, name="cart_remove"),
    path("cart/clear/", views.cart_clear, name="cart_clear"),
    path("checkout/thrift/", views.thrift_checkout, name="thrift_checkout"),
    path("checkout/thrift/payment/", views.thrift_payment, name="thrift_payment"),
    path("checkout/thrift/success/", views.thrift_success, name="thrift_success"),
    path("purchases/", views.purchase_list, name="purchases"),
    path("sales/", views.sales_list, name="sales"),
    path("<int:transaction_id>/", views.transaction_detail, name="detail"),
]
