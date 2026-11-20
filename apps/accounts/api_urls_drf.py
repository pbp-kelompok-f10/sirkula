from django.urls import path

from .api_views_drf import LoginView, LogoutView, ProfileView, RegisterView

app_name = 'accounts_api'

urlpatterns = [
    path('register/', RegisterView.as_view(), name='register'),
    path('login/', LoginView.as_view(), name='login'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('profile/', ProfileView.as_view(), name='profile'),
]
