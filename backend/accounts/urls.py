from django.urls import path
from .views import RegisterView, LoginView, AdminLoginView, forgot_password, reset_password, AdminLogoutView, AdminTokenRefreshView, UploadAvatarView, Me2View, MeView, UpdateProfileView
from . import views
from rest_framework_simplejwt.views import TokenRefreshView


urlpatterns = [
    path('register/', RegisterView.as_view()),
    path('login/', LoginView.as_view()),
        
    path("admin/login/", AdminLoginView.as_view(), name="admin-login"),
    path("admin/logout/", AdminLogoutView.as_view(), name="admin-logout"),
    path("admin/refresh/", AdminTokenRefreshView.as_view(), name="admin-refresh"),
    path("token/refresh/", TokenRefreshView.as_view(), name="token-refresh"),
    path('me/', MeView.as_view()),
    path('me2/', Me2View.as_view()),
    path("profile/update/", UpdateProfileView.as_view()),
    path('profile/upload-avatar/', UploadAvatarView.as_view(), name='profile-upload-avatar'),

    path("auth/forgot-password/", forgot_password),
    path("auth/reset-password/", reset_password),

    # Profile interactions
    path('profile/<int:user_id>/', views.UserProfileDetailView.as_view(), name='profile-detail'),
    path('profile/<int:target_id>/follow/', views.ToggleFollowView.as_view(), name='profile-follow'),
    path('profile/<int:target_id>/book/', views.ToggleStreamBookingView.as_view(), name='profile-book'),
]

