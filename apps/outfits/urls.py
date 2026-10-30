from django.urls import path

from . import views

app_name = "outfits"

urlpatterns = [
    path("", views.index, name="index"),
    path("conversations/<uuid:conversation_id>/", views.conversation, name="conversation"),
]
