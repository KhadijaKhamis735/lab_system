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
from django.contrib.auth.hashers import make_password
from decimal import Decimal

from .models import User, Department, Division, Customer, Sample, Test, Payment, Result, Ingredient
from .serializers import (
    LoginSerializer, UserSerializer, DepartmentSerializer, DivisionSerializer,
    CustomerSerializer, SampleDashboardSerializer, TestSerializer, PaymentSerializer, ResultSerializer,
    IngredientSerializer, RegisterSampleSerializer, CreateUserSerializer
)

logger = logging.getLogger(__name__)

# Custom permission class to check 'Admin' role
class IsAdmin(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == 'Admin'

# ===============================
# Authentication APIs
# ===============================
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
    except Exception as e:
        logger.error(f"Logout failed: {str(e)}")
        return Response({'success': False, 'message': 'Invalid token'}, status=status.HTTP_400_BAD_REQUEST)

@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def user_profile(request):
    return Response({'success': True, 'user': UserSerializer(request.user).data})

# ===============================
# Dashboards (role-guarded)
# ===============================
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
        return Response(
            {'success': False, 'message': 'Access denied. HOD role required.'},
            status=status.HTTP_403_FORBIDDEN
        )

    # Filter samples for this HOD's department only
    department_samples = Sample.objects.filter(
        registrar__department=request.user.department,
        status__in=['Registered', 'Awaiting HOD Review']
    )

    technicians = User.objects.filter(
        role='Technician',
        department=request.user.department
    ).values('id', 'username')

    return Response({
        'success': True,
        'role': 'HOD',
        'department_samples': SampleDashboardSerializer(department_samples, many=True).data,
        'technicians': list(technicians)
    })


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def registrar_dashboard(request):
    if request.user.role != 'Registrar':
        return Response({'success': False, 'message': 'Access denied. Registrar role required.'}, status=status.HTTP_403_FORBIDDEN)
    recent_samples = Sample.objects.filter(registrar=request.user).order_by('-date_received')[:10]
    related_tests = Test.objects.filter(sample__in=recent_samples).select_related('ingredient')
    return Response({
        'success': True,
        'role': 'Registrar',
        'recent_samples': SampleDashboardSerializer(recent_samples, many=True).data,
        'pending_tests': TestSerializer(related_tests, many=True).data
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

# ===============================
# Generic CRUD endpoints
# ===============================
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
    permission_classes = [permissions.IsAuthenticated]  # Changed from IsAdmin to IsAuthenticated

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        return Response({'success': True, 'ingredients': serializer.data})

    def create(self, request, *args, **kwargs):
        if request.user.role != 'Admin':  # Restrict creation to Admins
            return Response({'success': False, 'message': 'Only Admins can add ingredients.'}, status=status.HTTP_403_FORBIDDEN)
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(
            {'success': True, 'message': 'Ingredient added successfully.', 'ingredient': serializer.data},
            status=status.HTTP_201_CREATED,
            headers=headers
        )

# ===============================
# Sample Submission + Payments
# ===============================
@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
@transaction.atomic
def submit_sample_api(request):
    print(f"Request user: {request.user.username}, role: {request.user.role}")
    if request.user.role != 'Registrar':
        return Response({'success': False, 'message': 'Access denied. Registrar role required.'}, status=status.HTTP_403_FORBIDDEN)

    serializer = RegisterSampleSerializer(data=request.data, context={'request': request})
    print(f"Received data: {request.data}")
    if serializer.is_valid():
        try:
            samples = serializer.save()
            try:
                payment = Payment.objects.get(sample=samples[0])
            except Payment.DoesNotExist:
                payment = Payment.objects.create(sample=samples[0], status='Pending', amount_due=Decimal('0.00'))
            tests = Test.objects.filter(sample__in=samples)
            print(f"Submitted samples: {[s.control_number for s in samples]}")
            logger.info(f"Samples {', '.join(s.control_number for s in samples)} submitted by {request.user.username} to HOD: {samples[0].assigned_to_hod.username if samples[0].assigned_to_hod else 'None'}")
            return Response({
                'success': True,
                'message': 'Samples and tests submitted successfully.',
                'samples': SampleDashboardSerializer(samples, many=True).data,
                'payment': PaymentSerializer(payment).data,
                'tests': TestSerializer(tests, many=True).data
            }, status=status.HTTP_201_CREATED)
        except Exception as e:
            logger.error(f"Server error in submit_sample_api: {str(e)}")
            return Response({'success': False, 'message': f'Server error: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    else:
        print(f"Serializer errors: {serializer.errors}")
        return Response({'success': False, 'message': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def verify_payment_api(request, control_number):
    try:
        sample = Sample.objects.get(control_number=control_number)
        if random.random() > 0.5:
            sample.payment.status = 'Verified'
            sample.payment.verified_by = request.user
            sample.payment.verification_date = timezone.now()
            sample.payment.save()
            return Response({'success': True, 'message': 'Payment verified successfully.'})
        else:
            return Response({'success': False, 'message': 'Payment is still pending.'})
    except (Sample.DoesNotExist, Payment.DoesNotExist) as e:
        logger.error(f"Payment verification failed: {str(e)}")
        return Response({'success': False, 'message': 'Sample or Payment not found.'}, status=status.HTTP_404_NOT_FOUND)

# ===============================
# Assignment APIs
# ===============================
@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def assign_to_hodv_api(request, sample_id):
    return Response({'message': 'This endpoint is not yet implemented.'}, status=status.HTTP_501_NOT_IMPLEMENTED)

@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def assign_to_technician_api(request, sample_id):
    return Response({'message': 'This endpoint is not yet implemented.'}, status=status.HTTP_501_NOT_IMPLEMENTED)

@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def department_activities(request):
    return Response({'message': 'This endpoint is not yet implemented.'}, status=status.HTTP_501_NOT_IMPLEMENTED)

@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def pending_samples(request):
    return Response({'message': 'This endpoint is not yet implemented.'}, status=status.HTTP_501_NOT_IMPLEMENTED)

# ===============================
# Ingredients API
# ===============================
@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def ingredient_list_api(request):
    ingredients = Ingredient.objects.all()
    serializer = IngredientSerializer(ingredients, many=True)
    return Response({'success': True, 'ingredients': serializer.data})

# ===============================
# Registrar Samples API
# ===============================
@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def registrar_samples_api(request):
    if request.user.role != 'Registrar':
        return Response({'success': False, 'message': 'Access denied. Registrar role required.'}, status=status.HTTP_403_FORBIDDEN)
    recent_samples = Sample.objects.filter(registrar=request.user).order_by('-date_received').prefetch_related('test_set__ingredient')
    serializer = SampleDashboardSerializer(recent_samples, many=True)
    print(f"Serialized samples: {serializer.data}")
    return Response({'success': True, 'samples': serializer.data})

# ===============================
# Admin Add User
# ===============================
@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def admin_add_user(request):
    if request.user.role != 'Admin':
        return Response(
            {'success': False, 'message': 'Access denied. Admin role required.'},
            status=status.HTTP_403_FORBIDDEN
        )
    serializer = CreateUserSerializer(data=request.data)
    if serializer.is_valid():
        try:
            user = serializer.save()
            logger.info(f"New user {user.username} created by admin {request.user.username}")
            return Response(
                {'success': True, 'message': 'User created successfully.', 'user': UserSerializer(user).data},
                status=status.HTTP_201_CREATED
            )
        except Exception as e:
            logger.error(f"Error creating user: {str(e)}")
            return Response(
                {'success': False, 'message': f'Failed to create user: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    else:
        return Response({'success': False, 'message': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

# ===============================
# Technician Assigned Tests
# ===============================
@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def technician_assigned_tests(request):
    user = request.user
    if user.role != 'Technician':
        return Response({'success': False, 'message': 'Access denied. Technician role required.'}, status=status.HTTP_403_FORBIDDEN)
    tests = Test.objects.filter(assigned_to=user).select_related('sample', 'ingredient', 'assigned_to')
    logger.info(f"Technician {user.username} (ID: {user.id}) queried assigned tests, found {tests.count()} tests")
    if not tests.exists():
        logger.warning(f"No tests found for Technician {user.username} (ID: {user.id})")
    data = []
    for test in tests:
        logger.debug(f"Processing test {test.id}: assigned_to={test.assigned_to_id}, sample={test.sample.control_number}")
        data.append({
            'id': test.id,
            'sample': {
                'control_number': test.sample.control_number,
                'customer': {
                    'name': getattr(test.sample.customer, 'name', 'N/A'),
                },
                'date_received': test.sample.date_received.isoformat() if test.sample.date_received else None,
            },
            'ingredient': {
                'name': getattr(test.ingredient, 'name', None),
                'test_type': getattr(test.ingredient, 'test_type', None) if test.ingredient else None,
            },
            'assigned_by_hod': {
                'name': getattr(test.sample.assigned_to_hod, 'username', None) if test.sample.assigned_to_hod else None,
            },
            'status': test.status,
            'price': str(test.price) if test.price else None,
            'results': test.results if test.results else None,
        })
    logger.info(f"Returning {len(data)} tests for Technician {user.username}")
    return Response({'success': True, 'tests': data})

# ===============================
# Assign Technician to Sample
# ===============================
@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def assign_technician_to_sample(request):
    if request.user.role != 'HOD':
        return Response({'success': False, 'message': 'Access denied. HOD role required.'}, status=status.HTTP_403_FORBIDDEN)
    logger.debug(f"Current HOD assigning: {request.user.username}, ID: {request.user.id}, Role: {request.user.role}, Token User: {request.user}")
    sample_id = request.data.get('sample_id')
    technician_id = request.data.get('technician_id')
    try:
        with transaction.atomic():
            sample = Sample.objects.get(id=sample_id)
            if sample.status != 'Awaiting HOD Review':
                return Response({'success': False, 'message': 'Sample must be in Awaiting HOD Review status.'}, status=status.HTTP_400_BAD_REQUEST)
            technician = User.objects.get(id=technician_id, role='Technician')
            # Always set assigned_to_hod to the current HOD who is assigning
            sample.assigned_to_hod = request.user
            sample.save(update_fields=['assigned_to_hod'])
            logger.debug(f"Set assigned_to_hod for sample {sample.control_number} as {sample.assigned_to_hod.username}")
            sample.assign_to_technician(technician)
            logger.info(f"Assignment completed for sample {sample.control_number}, technician {technician.username} by HOD {request.user.username}")
            return Response({'success': True, 'message': 'Technician assigned successfully.'})
    except Sample.DoesNotExist:
        logger.error(f"Sample not found: ID {sample_id}")
        return Response({'success': False, 'message': 'Sample not found.'}, status=404)
    except User.DoesNotExist:
        logger.error(f"Technician not found: ID {technician_id}")
        return Response({'success': False, 'message': 'Technician not found.'}, status=404)
    except ValueError as e:
        logger.error(f"Invalid assignment: {str(e)}")
        return Response({'success': False, 'message': str(e)}, status=400)
    except Exception as e:
        logger.error(f"Assignment failed: {str(e)}")
        return Response({'success': False, 'message': str(e)}, status=500)