from rest_framework import serializers
from .models import VideoUpload
import os
import re


class VideoUploadSerializer(serializers.ModelSerializer):
    """Serializer for the VideoUpload model."""
    subtitle_url = serializers.SerializerMethodField()
    transcript_text = serializers.SerializerMethodField()
    
    class Meta:
        model = VideoUpload
        fields = ['id', 'video_file', 'status', 'error_message', 'created_at', 'subtitle_url', 'transcript_text']
        read_only_fields = ['id', 'status', 'error_message', 'created_at', 'subtitle_url', 'transcript_text']
    
    def get_subtitle_url(self, obj):
        """Get the URL for downloading the subtitle file if available."""
        if obj.subtitle_file and obj.status == 'completed':
            request = self.context.get('request')
            if request:
                # Return the API download endpoint URL instead of direct media URL
                # This ensures proper download behavior
                return request.build_absolute_uri(f'/api/download/{obj.id}/')
        return None
    
    def get_transcript_text(self, obj):
        """Get the transcript text from the subtitle file, converting SRT to plain text."""
        if obj.subtitle_file and obj.status == 'completed':
            try:
                subtitle_path = obj.subtitle_file.path
                if os.path.exists(subtitle_path):
                    with open(subtitle_path, 'r', encoding='utf-8') as f:
                        srt_content = f.read()
                    
                    # Convert SRT format to plain text
                    # SRT format: index number, timestamp, text lines, empty line
                    # Pattern: number\n timestamp\n text\n text\n\n
                    
                    # Split by double newlines to get subtitle blocks
                    blocks = re.split(r'\n\s*\n', srt_content.strip())
                    transcript_lines = []
                    
                    for block in blocks:
                        lines = block.strip().split('\n')
                        if len(lines) < 3:
                            continue
                        
                        # First line is index (number), second is timestamp, rest is text
                        timestamp_line = lines[1].strip() if len(lines) > 1 else ""
                        text_lines = lines[2:]
                        
                        # Extract start and end time from timestamp (format: 00:00:00,000 --> 00:00:05,000)
                        time_info = ""
                        if '-->' in timestamp_line:
                            times = timestamp_line.split('-->')
                            if len(times) == 2:
                                start_time = times[0].strip()
                                end_time = times[1].strip()
                                # Convert SRT time format to readable format (00:00:00,000 -> 00:00:00)
                                start_time_readable = start_time.replace(',', '.').split('.')[0]
                                end_time_readable = end_time.replace(',', '.').split('.')[0]
                                time_info = f"[{start_time_readable} - {end_time_readable}]"
                        
                        # Combine text lines
                        text_content = ' '.join([line.strip() for line in text_lines if line.strip() and '-->' not in line])
                        
                        if text_content:
                            # Format: [00:00:00 - 00:00:05] Text content
                            transcript_lines.append(f"{time_info} {text_content}")
                    
                    # Join all transcript lines with newlines
                    transcript = '\n\n'.join(transcript_lines)
                    
                    print(f"Extracted transcript length: {len(transcript)} characters")
                    print(f"Number of text lines extracted: {len(transcript_lines)}")
                    if transcript_lines:
                        print(f"First few lines: {transcript_lines[:3]}")
                    
                    # If transcript is empty, return None (not an error message)
                    if not transcript or len(transcript.strip()) == 0:
                        print("WARNING: Transcript is empty after extraction")
                        return None
                    
                    return transcript
            except Exception as e:
                print(f"Error reading transcript: {str(e)}")
                return None
        return None

    def validate_video_file(self, value):
        """Validate that the uploaded file is a video file (AVI or MP4)."""
        file_ext = value.name.lower().split('.')[-1]
        if file_ext not in ['avi', 'mp4']:
            raise serializers.ValidationError("Only AVI and MP4 video files are supported.")
        
        # Add a file size limit (100MB for example)
        if value.size > 100 * 1024 * 1024:  # 100MB
            raise serializers.ValidationError("Video file must be less than 100MB.")
            
        return value
    
    def create(self, validated_data):
        """Create a new VideoUpload instance with the current user."""
        # Get the user from the request context
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            validated_data['user'] = request.user
        else:
            raise serializers.ValidationError("User must be authenticated to upload videos.")
        
        return super().create(validated_data)