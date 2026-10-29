from django.urls import path

from . import views

app_name = "wardrobe"

urlpatterns = [
    path("", views.wardrobe, name="index"),
    path(
        "categories/add/",
        views.create_category,
        name="create_category",
    ),
    path(
        "items/add/",
        views.create_item,
        name="create_item",
    ),
    path(
        "photos/<int:photo_id>/",
        views.item_photo,
        name="item_photo",
    ),
    path(
    "items/<int:item_id>/",
    views.item_detail,
    name="item_detail",
    ),
    path(
    "items/<int:item_id>/edit/",
    views.update_item,
    name="update_item",
),
]
