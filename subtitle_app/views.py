from rest_framework import status, generics
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from django.http import FileResponse, HttpResponseNotFound, HttpResponse
from django.conf import settings
import os
from .models import VideoUpload
from .serializers import VideoUploadSerializer
from .subtitle_generator import generate_subtitles


class VideoUploadView(generics.CreateAPIView):
    """API endpoint for uploading videos and generating subtitles."""
    serializer_class = VideoUploadSerializer
    parser_classes = (MultiPartParser, FormParser)

    def post(self, request, *args, **kwargs):
        """Handle video upload and initiate subtitle generation."""
        # Check if user is authenticated
        if not request.user.is_authenticated:
            return Response(
                {'error': 'Authentication required to upload videos'}, 
                status=status.HTTP_401_UNAUTHORIZED
            )
        
        serializer = self.get_serializer(data=request.data)
        
        if serializer.is_valid():
            # Save the uploaded video
            video_upload = serializer.save()
            video_upload.status = 'processing'
            video_upload.save()
            
            try:
                # Generate subtitles (non-blocking)
                generate_subtitles(video_upload)
                
                # Return the response with the video ID
                response_serializer = VideoUploadSerializer(
                    video_upload, 
                    context={'request': request}
                )
                return Response(
                    response_serializer.data, 
                    status=status.HTTP_202_ACCEPTED
                )
            except Exception as e:
                # Update status if an error occurs
                import traceback
                error_traceback = traceback.format_exc()
                error_message = str(e)
                
                print(f"ERROR processing video {video_upload.id}:")
                print(f"Error message: {error_message}")
                print(f"Traceback:\n{error_traceback}")
                
                video_upload.status = 'failed'
                video_upload.error_message = error_message
                video_upload.save()
                
                return Response(
                    {
                        'error': 'Failed to process video',
                        'detail': error_message,
                        'traceback': error_traceback if settings.DEBUG else None
                    }, 
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
        
        return Response(
            serializer.errors, 
            status=status.HTTP_400_BAD_REQUEST
        )


class VideoStatusView(generics.RetrieveAPIView):
    """API endpoint for checking video processing status."""
    queryset = VideoUpload.objects.all()
    serializer_class = VideoUploadSerializer


class SubtitleDownloadView(generics.RetrieveAPIView):
    """API endpoint for downloading generated subtitle files."""
    queryset = VideoUpload.objects.all()
    
    def retrieve(self, request, *args, **kwargs):
        """Handle subtitle file download."""
        video_upload = self.get_object()
        
        if video_upload.status != 'completed' or not video_upload.subtitle_file:
            return Response(
                {'error': 'Subtitle file not available'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        
        subtitle_path = video_upload.subtitle_file.path
        
        if not os.path.exists(subtitle_path):
            return HttpResponseNotFound('Subtitle file not found')
        
        # Check if file is empty
        file_size = os.path.getsize(subtitle_path)
        print(f"Subtitle file path: {subtitle_path}")
        print(f"Subtitle file size: {file_size} bytes")
        
        if file_size == 0:
            return Response(
                {'error': 'Subtitle file is empty. Please regenerate subtitles.'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Return the file for download
        filename = os.path.basename(video_upload.video_file.name)
        base_filename = os.path.splitext(filename)[0]
        
        try:
            # Read file content as text to ensure proper encoding
            with open(subtitle_path, 'r', encoding='utf-8') as f:
                file_content = f.read()
            
            print(f"File content length: {len(file_content)} characters")
            print(f"File content preview (first 200 chars): {file_content[:200]}")
            
            # Check if content is actually empty (after reading)
            if not file_content or len(file_content.strip()) == 0:
                print("WARNING: File content is empty after reading!")
                return Response(
                    {'error': 'Subtitle file is empty. Please regenerate subtitles.'}, 
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # Create response with file content
            response = HttpResponse(file_content, content_type='text/plain; charset=utf-8')
            response['Content-Disposition'] = f'attachment; filename="{base_filename}.txt"'
            response['Content-Length'] = len(file_content.encode('utf-8'))
            
            return response
        except UnicodeDecodeError:
            # If UTF-8 fails, try reading as binary
            try:
                with open(subtitle_path, 'rb') as f:
                    file_content = f.read()
                
                if len(file_content) == 0:
                    return Response(
                        {'error': 'Subtitle file is empty. Please regenerate subtitles.'}, 
                        status=status.HTTP_404_NOT_FOUND
                    )
                
                response = HttpResponse(file_content, content_type='text/plain; charset=utf-8')
                response['Content-Disposition'] = f'attachment; filename="{base_filename}.txt"'
                response['Content-Length'] = len(file_content)
                
                return response
            except Exception as e:
                return Response(
                    {'error': f'Error reading subtitle file: {str(e)}'}, 
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
        except Exception as e:
            return Response(
                {'error': f'Error reading subtitle file: {str(e)}'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )