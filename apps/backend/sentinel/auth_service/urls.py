from django.urls import path

from sentinel.auth_service.views import (
    LoginView,
    LogoutView,
    MeView,
    PasswordChangeView,
    RegisterView,
    TokenRefreshView,
)

urlpatterns = [
    path("register/", RegisterView.as_view(), name="auth-register"),
    path("login/", LoginView.as_view(), name="auth-login"),
    path("refresh/", TokenRefreshView.as_view(), name="auth-refresh"),
    path("logout/", LogoutView.as_view(), name="auth-logout"),
    path("me/", MeView.as_view(), name="auth-me"),
    path("me/password/", PasswordChangeView.as_view(), name="auth-password-change"),
]
