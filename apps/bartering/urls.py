from django.urls import path

from . import views

app_name = "bartering"

urlpatterns = [
    path("checkout/<int:product_id>/", views.barter_chat, name="checkout"),
    path("checkout/<int:product_id>/mou/", views.barter_mou, name="mou"),
    path("checkout/<int:product_id>/payment/", views.barter_payment, name="payment"),
    path("checkout/success/", views.barter_success, name="success"),
    path("offers/create/<int:product_id>/", views.offer_create, name="offer_create"),
    path("offers/incoming/", views.incoming_offers, name="incoming"),
    path("offers/outgoing/", views.outgoing_offers, name="outgoing"),
    path("offers/<int:offer_id>/<str:status>/", views.update_offer_status, name="update_offer"),
    path("offers/<int:offer_id>/shipping/", views.update_shipping, name="update_shipping"),
    path("offers/<int:offer_id>/received/", views.confirm_received, name="confirm_received"),
]
