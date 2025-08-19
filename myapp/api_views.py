from django.http import JsonResponse
from rest_framework import generics, viewsets, permissions, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from django.db import transaction
from django.core.exceptions import ObjectDoesNotExist
import logging
from datetime import date
import random

from .models import User, Department, Division, Customer, Sample, Test, Payment, Result, Ingredient
from .serializers import (
    LoginSerializer, UserSerializer, DepartmentSerializer, DivisionSerializer,
    CustomerSerializer, SampleDashboardSerializer, TestSerializer, PaymentSerializer, ResultSerializer,
    IngredientSerializer, RegisterSampleSerializer
)

logger = logging.getLogger(__name__)

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

@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def admin_dashboard(request):
    if request.user.role != 'Admin':
        return Response(
            {'success': False, 'message': 'Access denied. Admin role required.'},
            status=status.HTTP_403_FORBIDDEN
        )
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
    
    department_samples = Sample.objects.filter(status__in=['Registered', 'Awaiting HOD Review'])
    
    return Response({
        'success': True, 
        'role': 'HOD', 
        'department_samples': SampleDashboardSerializer(department_samples, many=True).data
    })

@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def registrar_dashboard(request):
    if request.user.role != 'Registrar':
        return Response({'success': False, 'message': 'Access denied. Registrar role required.'}, status=status.HTTP_403_FORBIDDEN)
    
    recent_samples = Sample.objects.filter(registrar=request.user).order_by('-date_received')[:10]
    
    return Response({
        'success': True, 
        'role': 'Registrar', 
        'recent_samples': SampleDashboardSerializer(recent_samples, many=True).data
    })

@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def director_dashboard(request):
    if request.user.role != 'Director':
        return Response({'success': False, 'message': 'Access denied. Director role required.'}, status=status.HTTP_403_FORBIDDEN)
        
    pending_samples = Sample.objects.filter(status='Awaiting Director Confirmation')
    
    return Response({
        'success': True, 
        'role': 'Director', 
        'pending_approvals': SampleDashboardSerializer(pending_samples, many=True).data
    })

# Generic CRUD endpoints
class SampleListCreateAPI(generics.ListCreateAPIView):
    queryset = Sample.objects.all()
    serializer_class = SampleDashboardSerializer
    permission_classes = [permissions.IsAuthenticated]

class SampleRetrieveUpdateDestroyAPI(generics.RetrieveUpdateDestroyAPIView):
    queryset = Sample.objects.all()
    serializer_class = SampleDashboardSerializer
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

class IngredientViewSet(viewsets.ModelViewSet):
    queryset = Ingredient.objects.all()
    serializer_class = IngredientSerializer
    permission_classes = [permissions.IsAuthenticated]

# Sample Submission API
@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
@transaction.atomic
def submit_sample_api(request):
    if request.user.role != 'Registrar':
        return Response({'message': 'Access denied. Registrar role required.'}, status=status.HTTP_403_FORBIDDEN)

    serializer = RegisterSampleSerializer(data=request.data, context={'request': request})
    if serializer.is_valid():
        try:
            samples = serializer.save()
            for sample in samples:
                sample.registrar = request.user
                sample.submit_to_hod()  # may raise ValueError if no HOD/Dept
            payment = Payment.objects.get(sample=samples[0])  # Use first sample's payment
            tests = Test.objects.filter(sample__in=samples)
            logger.info(
                f"Samples {', '.join(s.control_number for s in samples)} "
                f"submitted by {request.user.username} "
                f"to HOD: {samples[0].assigned_to_hod.username if samples[0].assigned_to_hod else 'None'}"
            )
            return Response({
                'success': True,
                'message': 'Samples and tests submitted successfully.',
                'samples': SampleDashboardSerializer(samples, many=True).data,
                'payment': PaymentSerializer(payment).data,
                'tests': TestSerializer(tests, many=True).data
            }, status=status.HTTP_201_CREATED)
        
        except ValueError as e:
            return Response({'success': False, 'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}")
            return Response({'success': False, 'error': 'Unexpected server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    else:
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def verify_payment_api(request, control_number):
    try:
        sample = Sample.objects.get(control_number=control_number)
        
        # Mock payment verification logic
        if random.random() > 0.5:
            sample.payment.status = 'Verified'
            sample.payment.save()
            return Response({'success': True, 'message': 'Payment verified successfully.'})
        else:
            return Response({'success': False, 'message': 'Payment is still pending.'})
    except (Sample.DoesNotExist, Payment.DoesNotExist):
        return Response({'success': False, 'message': 'Sample or Payment not found.'}, status=status.HTTP_404_NOT_FOUND)

@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def assign_to_hodv_api(request, sample_id):
    # This is a placeholder. You need to add your own logic here.
    return Response({'message': 'This endpoint is not yet implemented.'}, status=status.HTTP_501_NOT_IMPLEMENTED)

@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def assign_to_technician_api(request, sample_id):
    # This is a placeholder. You need to add your own logic here.
    return Response({'message': 'This endpoint is not yet implemented.'}, status=status.HTTP_501_NOT_IMPLEMENTED)

@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def department_activities(request):
    # This is a placeholder. You need to add your own logic here.
    return Response({'message': 'This endpoint is not yet implemented.'}, status=status.HTTP_501_NOT_IMPLEMENTED)

@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def pending_samples(request):
    # This is a placeholder. You need to add your own logic here.
    return Response({'message': 'This endpoint is not yet implemented.'}, status=status.HTTP_501_NOT_IMPLEMENTED)

@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def ingredient_list_api(request):
    ingredients = Ingredient.objects.all()
    serializer = IngredientSerializer(ingredients, many=True)
    return Response({'success': True, 'ingredients': serializer.data})