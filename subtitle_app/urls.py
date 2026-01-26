from django.urls import path
from .views import VideoUploadView, SubtitleDownloadView, VideoStatusView
from .auth_views import register, login_view, logout_view, current_user, csrf_token

urlpatterns = [
    path('upload/', VideoUploadView.as_view(), name='upload_video'),
    path('upload/<int:pk>/', VideoStatusView.as_view(), name='video_status'),
    path('download/<int:pk>/', SubtitleDownloadView.as_view(), name='download_subtitle'),
    # Authentication endpoints
    path('auth/register/', register, name='register'),
    path('auth/login/', login_view, name='login'),
    path('auth/logout/', logout_view, name='logout'),
    path('auth/current-user/', current_user, name='current_user'),
    path('auth/csrf/', csrf_token, name='csrf_token'),
]