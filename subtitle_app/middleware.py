from django.utils.deprecation import MiddlewareMixin
from django.conf import settings


class EnsureCORSForAPI(MiddlewareMixin):
    """Ensure CORS headers on all API responses (including errors) when origin is allowed."""
    
    def process_response(self, request, response):
        if not request.path.startswith('/api/'):
            return response
        if response.get('Access-Control-Allow-Origin'):
            return response
        origin = request.META.get('HTTP_ORIGIN')
        if not origin:
            return response
        allowed = getattr(settings, 'CORS_ALLOWED_ORIGINS', [])
        if origin in allowed:
            response['Access-Control-Allow-Origin'] = origin
            if getattr(settings, 'CORS_ALLOW_CREDENTIALS', False):
                response['Access-Control-Allow-Credentials'] = 'true'
        return response


class DisableCSRFForAPI(MiddlewareMixin):
    """Middleware to disable CSRF for API endpoints."""
    
    def process_request(self, request):
        # Disable CSRF for logout and upload endpoints
        api_paths = [
            '/api/auth/logout/',
            '/api/upload/',
        ]
        if request.path in api_paths or request.path.startswith('/api/upload/'):
            setattr(request, '_dont_enforce_csrf_checks', True)
        return None
