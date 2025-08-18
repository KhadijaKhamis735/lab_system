from decimal import Decimal
from django.contrib.auth import authenticate, login, logout
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib import messages
from rest_framework import generics, viewsets, permissions, status
from django.http import JsonResponse
from django.shortcuts import render, redirect
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)

from .models import (
    User, Department, Division, Customer, Sample, Test, Payment, Result, Ingredient
)

from .serializers import (
    LoginSerializer, UserSerializer, DepartmentSerializer, DivisionSerializer,
    CustomerSerializer, SampleSerializer, TestSerializer, PaymentSerializer, ResultSerializer,
    RegisterSampleSerializer, IngredientSerializer
)

# Root
def root_view(request):
    return JsonResponse({'success': True, 'message': 'Welcome to the Lab API'})

# Web views
def web_login_view(request):
    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")
        user = authenticate(request, username=username, password=password)
        if user:
            login(request, user)
            return redirect("home")
        else:
            messages.error(request, "Invalid username or password")
    return render(request, "login.html")

def home_view(request):
    return render(request, "home.html")

def web_logout_view(request):
    logout(request)
    return redirect("login_web")

# API Authentication
@api_view(["POST"])
@permission_classes([permissions.AllowAny])
def login_api(request):
    serializer = LoginSerializer(data=request.data, context={'request': request})
    if serializer.is_valid():
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
    return Response({'success': False, 'errors': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

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

# Dashboards
@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def technician_dashboard(request):
    if getattr(request.user, 'role', '') != 'Technician':
        return Response({'success': False, 'message': 'Access denied. Technician role required.'}, status=status.HTTP_403_FORBIDDEN)
    assigned_tests = Test.objects.filter(assigned_to=request.user)
    return Response({'success': True, 'role': 'Technician', 'assigned_tests': TestSerializer(assigned_tests, many=True).data})

@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def hod_dashboard(request):
    try:
        if getattr(request.user, 'role', '') != 'HOD':
            return Response({'success': False, 'message': 'Access denied. HOD role required.'}, status=status.HTTP_403_FORBIDDEN)
        department_samples = Sample.objects.filter(status='Awaiting HOD Review', assigned_to_hod=request.user)
        logger.info(f"HOD {request.user.username} fetched {department_samples.count()} samples")
        if not department_samples.exists():
            logger.info("No samples found for HOD")
            return Response({
                'success': True,
                'role': 'HOD',
                'stats': {'departmentSamples': 0, 'pendingTests': 0, 'teamMembers': 0},
                'department_samples': []
            })
        stats = {
            'departmentSamples': department_samples.count(),
            'pendingTests': Test.objects.filter(sample__in=department_samples, status='Pending').count(),
            'teamMembers': User.objects.filter(division_id=request.user.division_id).count() if request.user.division_id else 0
        }
        return Response({
            'success': True,
            'role': 'HOD',
            'stats': stats,
            'department_samples': SampleSerializer(department_samples, many=True).data
        })
    except Exception as e:
        logger.error(f"HOD dashboard error: {str(e)}")
        return Response({'success': False, 'message': f'Internal server error: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def registrar_dashboard(request):
    if getattr(request.user, 'role', '') != 'Registrar':
        return Response({'success': False, 'message': 'Access denied. Registrar role required.'}, status=status.HTTP_403_FORBIDDEN)
    recent_samples = Sample.objects.filter(registrar=request.user).order_by('-date_received')[:10]
    pending_payments = Payment.objects.filter(sample__registrar=request.user, status='Pending')
    return Response({
        'success': True,
        'role': 'Registrar',
        'recent_samples': SampleSerializer(recent_samples, many=True).data,
        'pending_payments': PaymentSerializer(pending_payments, many=True).data
    })

@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def director_dashboard(request):
    if getattr(request.user, 'role', '') != 'Director':
        return Response({'success': False, 'message': 'Access denied. Director role required.'}, status=status.HTTP_403_FORBIDDEN)
    pending_samples = Sample.objects.filter(status='Awaiting Director Confirmation')
    return Response({
        'success': True,
        'role': 'Director',
        'pending_approvals': SampleSerializer(pending_samples, many=True).data
    })

@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def admin_dashboard(request):
    if getattr(request.user, 'role', '') != 'Admin':
        return Response({'success': False, 'message': 'Access denied. Admin role required.'}, status=status.HTTP_403_FORBIDDEN)
    total_users = User.objects.count()
    total_departments = Department.objects.count()
    total_samples = Sample.objects.count()
    total_tests = Test.objects.count()
    return Response({
        'success': True,
        'role': 'Admin',
        'stats': {
            'total_users': total_users,
            'total_departments': total_departments,
            'total_samples': total_samples,
            'total_tests': total_tests,
        }
    })

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

# ViewSets
class IngredientViewSet(viewsets.ModelViewSet):
    queryset = Ingredient.objects.all().order_by('name')
    serializer_class = IngredientSerializer
    permission_classes = [permissions.IsAuthenticated]

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

# Custom Views
@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def submit_sample_api(request):
    if getattr(request.user, 'role', '') != 'Registrar':
        return Response({'success': False, 'message': 'Access denied. Registrar role required.'}, status=status.HTTP_403_FORBIDDEN)

    serializer = RegisterSampleSerializer(data=request.data, context={'request': request})
    if serializer.is_valid():
        sample = serializer.save()
        sample.registrar = request.user
        try:
            sample.submit_to_hod()
            payment = Payment.objects.get(sample=sample)
            tests = Test.objects.filter(sample=sample)
            logger.info(
                f"Sample {sample.control_number} submitted by {request.user.username} "
                f"to HOD: {sample.assigned_to_hod.username if sample.assigned_to_hod else 'None'}"
            )
            return Response({
                'success': True,
                'sample': SampleSerializer(sample).data,
                'payment': PaymentSerializer(payment).data,
                'tests': TestSerializer(tests, many=True).data
            }, status=status.HTTP_201_CREATED)
        except Exception as e:
            logger.error(f"Failed to submit sample to HOD: {str(e)}")
            return Response({'success': False, 'message': f'Failed to assign HOD: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    logger.error(f"Validation errors: {serializer.errors}")
    return Response({'success': False, 'errors': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def assign_to_hodv_api(request, sample_id):
    if getattr(request.user, 'role', '') != 'HOD':
        return Response({'success': False, 'message': 'Access denied. HOD role required.'}, status=status.HTTP_403_FORBIDDEN)
    try:
        sample = Sample.objects.get(id=sample_id, assigned_to_hod=request.user, status='Awaiting HOD Review')
        hodv_user = User.objects.filter(role='HODv', division=sample.registrar.division).first()
        if hodv_user:
            sample.status = 'Awaiting HODv Assignment'
            sample.assigned_to_hodv = hodv_user
            sample.assigned_to_hod = None
            sample.save()
            return Response({'success': True, 'message': 'Sample assigned to HODv'}, status=status.HTTP_200_OK)
        return Response({'success': False, 'message': 'No HODv available'}, status=status.HTTP_400_BAD_REQUEST)
    except Sample.DoesNotExist:
        return Response({'success': False, 'message': 'Sample not found or permission denied'}, status=status.HTTP_404_NOT_FOUND)

@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def assign_to_technician_api(request, sample_id):
    if getattr(request.user, 'role', '') != 'HODv':
        return Response({'success': False, 'message': 'Access denied. HODv role required.'}, status=status.HTTP_403_FORBIDDEN)
    try:
        sample = Sample.objects.get(id=sample_id, assigned_to_hodv=request.user, status='Awaiting HODv Assignment')
        technician_user = User.objects.filter(role='Technician', division=sample.registrar.division).first()
        if technician_user:
            sample.status = 'In Progress'
            sample.assigned_to_technician = technician_user
            sample.assigned_to_hodv = None
            sample.save()
            return Response({'success': True, 'message': 'Sample assigned to Technician'}, status=status.HTTP_200_OK)
        return Response({'success': False, 'message': 'No Technician available'}, status=status.HTTP_400_BAD_REQUEST)
    except Sample.DoesNotExist:
        return Response({'success': False, 'message': 'Sample not found or permission denied'}, status=status.HTTP_404_NOT_FOUND)

@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def verify_payment_api(request, control_number):
    if getattr(request.user, 'role', '') != 'Registrar':
        return Response({'success': False, 'message': 'Access denied. Registrar role required.'}, status=status.HTTP_403_FORBIDDEN)
    try:
        sample = Sample.objects.get(control_number=control_number)
        payment = Payment.objects.get(sample=sample)
        if payment.status == 'Verified':
            return Response({'success': False, 'message': 'Payment already verified.'}, status=status.HTTP_400_BAD_REQUEST)
        payment.status = 'Verified'
        payment.verified_by = request.user
        payment.verification_date = timezone.now()
        payment.save()
        return Response({'success': True, 'payment': PaymentSerializer(payment).data})
    except Sample.DoesNotExist:
        return Response({'success': False, 'message': 'Sample not found.'}, status=status.HTTP_404_NOT_FOUND)
    except Payment.DoesNotExist:
        return Response({'success': False, 'message': 'Payment not found.'}, status=status.HTTP_404_NOT_FOUND)

@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def department_activities(request):
    if getattr(request.user, 'role', '') != 'HOD':
        return Response({'success': False, 'message': 'Access denied. HOD role required.'}, status=status.HTTP_403_FORBIDDEN)
    recent_activities = [
        f"Sample {s.id} submitted by {s.registrar.username} on {s.date_received}"
        for s in Sample.objects.filter(assigned_to_hod=request.user).order_by('-date_received')[:5]
    ]
    return Response({'success': True, 'recent_activities': recent_activities})

@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def pending_samples(request):
    if getattr(request.user, 'role', '') != 'HOD':
        return Response({'success': False, 'message': 'Access denied. HOD role required.'}, status=status.HTTP_403_FORBIDDEN)
    pending_samples = Sample.objects.filter(status='Awaiting HOD Review', assigned_to_hod=request.user)
    serialized_samples = SampleSerializer(pending_samples, many=True).data
    flattened_samples = [
        {
            'id': sample['id'],
            'customerName': sample['customer']['name'],
            'customerPhone': sample['customer'].get('phone_number', 'N/A'),
            'customerEmail': sample['customer'].get('email', 'N/A'),
            'customerAddress': sample['customer'].get('address', 'N/A'),
            'sampleType': sample.get('sample_details', 'N/A'),
            'controlNumber': sample.get('control_number', ''),
            'status': sample.get('status', 'N/A'),
            'date': sample.get('date_received', sample.get('date', 'N/A'))
        }
        for sample in serialized_samples
    ]
    return Response({'success': True, 'samples': flattened_samples})
