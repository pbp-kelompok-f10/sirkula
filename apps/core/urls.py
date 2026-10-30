from django.urls import path

from . import views

app_name = "core"

urlpatterns = [
    path("", views.home, name="home"),
    path("components/", views.show_components, name="show_components"),
    path("reviews/new/", views.review_create, name="review_create"),
    path("reviews/<int:pk>/edit/", views.review_update, name="review_update"),
    path("reviews/<int:pk>/delete/", views.review_delete, name="review_delete"),
    path("reviews/<int:pk>/like/", views.review_like, name="review_like"),
]
