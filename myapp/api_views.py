from django.http import JsonResponse
from rest_framework import generics, viewsets, permissions, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken

from .models import User, Department, Division, Customer, Sample, Test, Payment, Result
from .serializers import (
    LoginSerializer, UserSerializer, DepartmentSerializer, DivisionSerializer,
    CustomerSerializer, SampleSerializer, TestSerializer, PaymentSerializer, ResultSerializer
)

# Root
def root_view(request):
    return JsonResponse({'success': True, 'message': 'Welcome to the Lab API'})

# Authentication APIs
@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def login_api(request):
    serializer = LoginSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    user = serializer.validated_data['user']
    refresh = RefreshToken.for_user(user)
    user_data = UserSerializer(user).data
    return Response({
        'success': True,
        'message': 'Login successful',
        'user': user_data,
        'tokens': {
            'access': str(refresh.access_token),
            'refresh': str(refresh)
        }
    }, status=status.HTTP_200_OK)

@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def logout_api(request):
    try:
        refresh_token = request.data.get("refresh")
        token = RefreshToken(refresh_token)
        token.blacklist()
        return Response({'success': True, 'message': 'Logout successful'}, status=status.HTTP_200_OK)
    except Exception:
        return Response({'success': False, 'message': 'Invalid token'}, status=status.HTTP_400_BAD_REQUEST)

@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def user_profile(request):
    return Response({'success': True, 'user': UserSerializer(request.user).data})

# Dashboards (role-guarded)
@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def technician_dashboard(request):
    if request.user.role != 'Technician':
        return Response({'success': False, 'message': 'Access denied. Technician role required.'}, status=status.HTTP_403_FORBIDDEN)
    assigned_tests = Test.objects.filter(assigned_to=request.user)
    return Response({'success': True, 'role': 'Technician', 'assigned_tests': TestSerializer(assigned_tests, many=True).data})

@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def hod_dashboard(request):
    if request.user.role != 'HOD':
        return Response({'success': False, 'message': 'Access denied. HOD role required.'}, status=status.HTTP_403_FORBIDDEN)
    department_samples = Sample.objects.filter(status__in=['Registered', 'Awaiting HOD Confirmation'])
    return Response({'success': True, 'role': 'HOD', 'department_samples': SampleSerializer(department_samples, many=True).data})

@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def registrar_dashboard(request):
    if request.user.role != 'Registrar':
        return Response({'success': False, 'message': 'Access denied. Registrar role required.'}, status=status.HTTP_403_FORBIDDEN)
    recent_samples = Sample.objects.filter(registrar=request.user).order_by('-date_received')[:10]
    return Response({'success': True, 'role': 'Registrar', 'recent_samples': SampleSerializer(recent_samples, many=True).data})

@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def director_dashboard(request):
    if request.user.role != 'Director':
        return Response({'success': False, 'message': 'Access denied. Director role required.'}, status=status.HTTP_403_FORBIDDEN)
    pending_samples = Sample.objects.filter(status='Awaiting Director Confirmation')
    return Response({'success': True, 'role': 'Director', 'pending_approvals': SampleSerializer(pending_samples, many=True).data})

# Generic CRUD endpoints
class SampleListCreateAPI(generics.ListCreateAPIView):
    queryset = Sample.objects.all()
    serializer_class = SampleSerializer
    permission_classes = [permissions.IsAuthenticated]

class SampleRetrieveUpdateDestroyAPI(generics.RetrieveUpdateDestroyAPIView):
    queryset = Sample.objects.all()
    serializer_class = SampleSerializer
    permission_classes = [permissions.IsAuthenticated]

class TestListCreateAPI(generics.ListCreateAPIView):
    queryset = Test.objects.all()
    serializer_class = TestSerializer
    permission_classes = [permissions.IsAuthenticated]

class TestRetrieveUpdateDestroyAPI(generics.RetrieveUpdateDestroyAPIView):
    queryset = Test.objects.all()
    serializer_class = TestSerializer
    permission_classes = [permissions.IsAuthenticated]

# ViewSets for admin CRUD
class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

class DepartmentViewSet(viewsets.ModelViewSet):
    queryset = Department.objects.all()
    serializer_class = DepartmentSerializer
    permission_classes = [permissions.IsAuthenticated]

class DivisionViewSet(viewsets.ModelViewSet):
    queryset = Division.objects.all()
    serializer_class = DivisionSerializer
    permission_classes = [permissions.IsAuthenticated]

class CustomerViewSet(viewsets.ModelViewSet):
    queryset = Customer.objects.all()
    serializer_class = CustomerSerializer
    permission_classes = [permissions.IsAuthenticated]

class PaymentViewSet(viewsets.ModelViewSet):
    queryset = Payment.objects.all()
    serializer_class = PaymentSerializer
    permission_classes = [permissions.IsAuthenticated]

class ResultViewSet(viewsets.ModelViewSet):
    queryset = Result.objects.all()
    serializer_class = ResultSerializer
    permission_classes = [permissions.IsAuthenticated]
