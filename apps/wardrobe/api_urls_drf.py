from django.urls import path

from .api_views_drf import CategoryDetail, CategoryList, ItemDetail, ItemList, PhotoDetail

app_name = "wardrobe_drf"

urlpatterns = [
    path("categories/", CategoryList.as_view(), name="categories"),
    path("categories/<int:pk>/", CategoryDetail.as_view(), name="category"),
    path("items/", ItemList.as_view(), name="items"),
    path("items/<int:pk>/", ItemDetail.as_view(), name="item"),
    path("photos/<int:photo_id>/", PhotoDetail.as_view(), name="photo"),
]
