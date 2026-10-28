from django.urls import path

from . import views

app_name = "wardrobe"

urlpatterns = [
    path("", views.wardrobe, name="index"),
    path("categories/add/", views.create_category, name="create_category"),
]
