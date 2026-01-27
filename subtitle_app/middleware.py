from django.utils.deprecation import MiddlewareMixin

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
