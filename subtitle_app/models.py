from django.db import models
from django.contrib.auth.models import User
import os
import uuid


def video_upload_path(instance, filename):
    """Generate a unique path for uploaded videos."""
    ext = filename.split('.')[-1]
    filename = f"{uuid.uuid4()}.{ext}"
    return os.path.join('videos', filename)


def subtitle_upload_path(instance, filename):
    """Generate a unique path for generated subtitle files."""
    return os.path.join('subtitles', f"{uuid.uuid4()}.srt")


class VideoUpload(models.Model):
    """Model to track uploaded videos and their generated subtitles."""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='video_uploads', null=True, blank=True)
    video_file = models.FileField(upload_to=video_upload_path)
    subtitle_file = models.FileField(upload_to=subtitle_upload_path, blank=True, null=True)
    status = models.CharField(
        max_length=20, 
        choices=[
            ('pending', 'Pending'),
            ('processing', 'Processing'),
            ('completed', 'Completed'),
            ('failed', 'Failed'),
        ],
        default='pending'
    )
    error_message = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Video Upload {self.id} - {self.status}"

    def filename(self):
        return os.path.basename(self.video_file.name)

    def delete(self, *args, **kwargs):
        # Delete the files when the model instance is deleted
        if self.video_file:
            if os.path.isfile(self.video_file.path):
                os.remove(self.video_file.path)
        
        if self.subtitle_file:
            if os.path.isfile(self.subtitle_file.path):
                os.remove(self.subtitle_file.path)
        
        super().delete(*args, **kwargs)