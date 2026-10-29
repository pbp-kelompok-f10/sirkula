from django.urls import path

from . import views

app_name = "bartering"

urlpatterns = [
    path("checkout/<int:product_id>/", views.barter_chat, name="checkout"),
    path("checkout/<int:product_id>/mou/", views.barter_mou, name="mou"),
    path("checkout/<int:product_id>/payment/", views.barter_payment, name="payment"),
    path("checkout/success/", views.barter_success, name="success"),
]
