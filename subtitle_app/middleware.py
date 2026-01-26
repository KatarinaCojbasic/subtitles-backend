from django.utils.deprecation import MiddlewareMixin

class DisableCSRFForAPI(MiddlewareMixin):
    """Middleware to disable CSRF for API endpoints."""
    
    def process_request(self, request):
        # Disable CSRF for logout endpoint
        if request.path == '/api/auth/logout/':
            setattr(request, '_dont_enforce_csrf_checks', True)
        return None
