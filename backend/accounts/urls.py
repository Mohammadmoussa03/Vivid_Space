from django.urls import path

from .views import (
    CookieTokenRefreshView,
    CsrfView,
    GoogleLoginView,
    LoginView,
    LogoutView,
    MeView,
    PasswordResetConfirmView,
    PasswordResetView,
    RegisterView,
    ResendVerificationView,
    VerifyEmailView,
)

urlpatterns = [
    path('register/', RegisterView.as_view(), name='register'),
    path('login/', LoginView.as_view(), name='login'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('social/google/', GoogleLoginView.as_view(), name='social_google'),
    path('token/refresh/', CookieTokenRefreshView.as_view(), name='token_refresh'),
    path('csrf/', CsrfView.as_view(), name='csrf'),
    path('password-reset/', PasswordResetView.as_view(), name='password_reset'),
    path('password-reset/confirm/', PasswordResetConfirmView.as_view(), name='password_reset_confirm'),
    path('verify-email/', VerifyEmailView.as_view(), name='verify_email'),
    path('resend-verification/', ResendVerificationView.as_view(), name='resend_verification'),
    path('me/', MeView.as_view(), name='me'),
]
