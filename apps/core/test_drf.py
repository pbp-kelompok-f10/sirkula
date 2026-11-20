from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

from .models import Review


class ReviewAPITests(APITestCase):
    def test_review_permissions_and_likes(self):
        user = get_user_model().objects.create_user(username="author", password="test-password")
        other = get_user_model().objects.create_user(username="other", password="test-password")
        self.client.force_authenticate(user)
        response = self.client.post("/api/v1/core/reviews/", {"content": "A useful application"}, format="json")
        self.assertEqual(response.status_code, 201)
        pk = response.data["id"]
        self.assertEqual(self.client.post("/api/v1/core/reviews/", {"content": "Another review"}, format="json").status_code, 400)
        self.assertEqual(self.client.put(f"/api/v1/core/reviews/{pk}/like/").status_code, 403)
        self.client.force_authenticate(other)
        self.assertEqual(self.client.patch(f"/api/v1/core/reviews/{pk}/", {"content": "Changed review"}, format="json").status_code, 403)
        response = self.client.put(f"/api/v1/core/reviews/{pk}/like/")
        self.assertEqual(response.data["like_count"], 1)
        self.assertEqual(Review.objects.get(pk=pk).content, "A useful application")
