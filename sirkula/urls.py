from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("apps.core.urls")),
    path("wardrobe/", include("apps.wardrobe.urls")),
    # Upstream routes below await urls.py files from the respective app owners.
    # path("accounts/", include("apps.accounts.urls")),
    # path("marketplace/", include("apps.marketplace.urls")),
    # path("barter/", include("apps.bartering.urls")),
    # path("outfits/", include("apps.outfits.urls")),
]
