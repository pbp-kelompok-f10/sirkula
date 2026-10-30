from django.urls import path

from . import views, preview_views

app_name = "outfits"

urlpatterns = [
    path("conversations/<uuid:conversation_id>/preview/", preview_views.preview, name="preview"),
    path("conversations/<uuid:conversation_id>/preview/image/", preview_views.preview_image, name="preview_image"),
    path("", views.index, name="index"),
    path("conversations/<uuid:conversation_id>/", views.conversation, name="conversation"),
]
