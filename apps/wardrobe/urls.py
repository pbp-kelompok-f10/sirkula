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
    path(
        "items/<int:item_id>/delete/",
        views.delete_item,
        name="delete_item",
    ),
    path(
    "categories/<int:category_id>/edit/",
    views.update_category,
    name="update_category",
    ),
    path(
        "categories/<int:category_id>/delete/",
        views.delete_category,
        name="delete_category",
    ),
    path(
        "draft/",
        views.current_draft,
        name="current_draft",
    ),
    path(
        "draft/save/",
        views.save_draft,
        name="save_draft",
    ),
    path(
        "draft/complete/",
        views.complete_draft,
        name="complete_draft",
    ),
    path(
        "draft/discard/",
        views.discard_draft,
        name="discard_draft",
    ),
]
