from django.urls import path

from .api_views_drf import ConversationDetail, ConversationMessages, Conversations, Preview, PreviewImage

app_name = "outfits_drf"

urlpatterns = [
    path("conversations/", Conversations.as_view(), name="conversations"),
    path("conversations/<uuid:pk>/", ConversationDetail.as_view(), name="conversation"),
    path("conversations/<uuid:pk>/messages/", ConversationMessages.as_view(), name="messages"),
    path("conversations/<uuid:pk>/preview/", Preview.as_view(), name="preview"),
    path("conversations/<uuid:pk>/preview/image/", PreviewImage.as_view(), name="preview_image"),
]
