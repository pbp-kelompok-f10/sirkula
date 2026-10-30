from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    # auth
    path("login/", views.SirkulaLoginView.as_view(), name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("register/", views.register, name="register"),
    path("register/location/", views.register_location, name="register_location"),

    # profil
    path("me/", views.my_profile, name="me"),
    path("u/<str:username>/", views.profile_detail, name="profile"),

    # pengaturan
    path("edit/", views.profile_edit, name="profile_edit"),
    path("account/", views.account_edit, name="account_edit"),
    path("password/", views.PasswordChangeViewStyled.as_view(), name="password_change"),
    path("delete/", views.delete_account, name="delete_account"),
]
