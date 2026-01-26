from django.contrib import admin
from .models import VideoUpload

@admin.register(VideoUpload)
class VideoUploadAdmin(admin.ModelAdmin):
    list_display = ('id', 'filename', 'status', 'created_at', 'updated_at')
    list_filter = ('status', 'created_at')
    search_fields = ('video_file', 'status')
    readonly_fields = ('created_at', 'updated_at')