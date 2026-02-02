from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.authtoken.models import Token
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.db import transaction


@api_view(['POST'])
@permission_classes([AllowAny])
def register(request):
    """User registration endpoint with key validation."""
    print(f"Registration request received: {request.method}")
    print(f"Request data: {request.data}")
    print(f"Content-Type: {request.content_type}")
    
    data = request.data
    
    # Validate required fields
    required_fields = ['first_name', 'last_name', 'email', 'password', 'key']
    for field in required_fields:
        if field not in data:
            print(f"Missing field: {field}")
            return Response(
                {'error': f'Missing required field: {field}'},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    # Validate registration key
    print(f"Registration key received: '{data.get('key')}'")
    if data['key'] != '1234567':
        print(f"Invalid registration key: '{data.get('key')}'")
        return Response(
            {'error': 'Invalid registration key'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Check if user with this email already exists
    if User.objects.filter(email=data['email']).exists():
        return Response(
            {'error': 'User with this email already exists'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Check if username (email) already exists
    if User.objects.filter(username=data['email']).exists():
        return Response(
            {'error': 'User with this email already exists'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        with transaction.atomic():
            # Create user
            user = User.objects.create_user(
                username=data['email'],
                email=data['email'],
                password=data['password'],
                first_name=data['first_name'],
                last_name=data['last_name']
            )
            
            return Response(
                {
                    'message': 'User registered successfully',
                    'user': {
                        'id': user.id,
                        'email': user.email,
                        'first_name': user.first_name,
                        'last_name': user.last_name,
                    }
                },
                status=status.HTTP_201_CREATED
            )
    except Exception as e:
        return Response(
            {'error': f'Registration failed: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([AllowAny])
def login_view(request):
    """User login endpoint."""
    data = request.data
    
    if 'email' not in data or 'password' not in data:
        return Response(
            {'error': 'Email and password are required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Authenticate user (username is email in our case)
    user = authenticate(request, username=data['email'], password=data['password'])
    
    if user is not None:
        token, _ = Token.objects.get_or_create(user=user)
        return Response(
            {
                'message': 'Login successful',
                'token': token.key,
                'user': {
                    'id': user.id,
                    'email': user.email,
                    'first_name': user.first_name,
                    'last_name': user.last_name,
                }
            },
            status=status.HTTP_200_OK
        )
    else:
        return Response(
            {'error': 'Invalid email or password'},
            status=status.HTTP_401_UNAUTHORIZED
        )


@api_view(['POST'])
@permission_classes([AllowAny])
def logout_view(request):
    """User logout endpoint. Invalidates token when authenticated via token."""
    if request.user.is_authenticated:
        Token.objects.filter(user=request.user).delete()
        logout(request)
    return Response(
        {'message': 'Logout successful'},
        status=status.HTTP_200_OK
    )


@api_view(['GET'])
@permission_classes([AllowAny])
def current_user(request):
    """Get current logged in user."""
    if request.user.is_authenticated:
        return Response(
            {
                'user': {
                    'id': request.user.id,
                    'email': request.user.email,
                    'first_name': request.user.first_name,
                    'last_name': request.user.last_name,
                }
            },
            status=status.HTTP_200_OK
        )
    else:
        return Response(
            {'user': None},
            status=status.HTTP_200_OK
        )


@api_view(['GET'])
@permission_classes([AllowAny])
def csrf_token(request):
    """Get CSRF token for frontend."""
    from django.middleware.csrf import get_token
    token = get_token(request)
    return Response({'csrfToken': token}, status=status.HTTP_200_OK)
