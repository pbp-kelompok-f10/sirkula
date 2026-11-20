from rest_framework.routers import DefaultRouter

from .api_views import ReviewViewSet

router = DefaultRouter()
router.register("reviews", ReviewViewSet, basename="review")
urlpatterns = router.urls
