from django.http import JsonResponse
from rest_framework import viewsets, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from django.db import transaction
import logging
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from datetime import timedelta
from django.utils import timezone
from rest_framework.permissions import IsAuthenticated, AllowAny, BasePermission
from rest_framework.views import APIView
import random
from django.contrib.auth.hashers import make_password
from decimal import Decimal
from django.core.mail import send_mail
from django.db.models import Q
from django.utils.crypto import get_random_string
from django.urls import reverse

from .models import (
    User, Department, Division, Customer, Sample, Test, Payment, Result, Ingredient, VerificationToken
)
from .serializers import (
    LoginSerializer, UserSerializer, DepartmentSerializer, DivisionSerializer,
    CustomerSerializer, SampleDashboardSerializer, TestSerializer, PaymentSerializer, ResultSerializer,
    IngredientSerializer, RegisterSampleSerializer, CreateUserSerializer, UnclaimedSampleSerializer,
    FullSampleSerializer, TechnicianDashboardSerializer    # ✅ add this import
)

logger = logging.getLogger(__name__)


class IsAdmin(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == 'Admin'


# -------------------------------------------------------
# Public: Customer submits samples without login
# -------------------------------------------------------
# -------------------------------------------------------
# Public: Customer submits samples without login
# -------------------------------------------------------
# views.py


class CustomerSubmitSampleAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        customer_data = request.data.get("customer", {})
        samples_data = request.data.get("samples", [])

        # Remove invalid keys
        customer_data.pop("submission_date", None)
        customer_data.pop("submission_time", None)

        phone_number = customer_data.get("phone_number")
        email = customer_data.get("email")

        # Try to get existing customer by phone_number OR email
        customer = None
        if phone_number:
            customer = Customer.objects.filter(phone_number=phone_number).first()
        if not customer and email:
            customer = Customer.objects.filter(email=email).first()

        if customer:
            # Update details if customer already exists
            for field, value in customer_data.items():
                setattr(customer, field, value)
            customer.save()
        else:
            # Create new customer
            customer = Customer.objects.create(**customer_data)

        # ---- Save Samples ----
        saved_samples = []
        for sample_data in samples_data:
            sample = Sample.objects.create(
                customer=customer,
                sample_name=sample_data.get("name"),
                sample_details=sample_data.get("sample_details", ""),
                status="Awaiting Registrar Approval",
                date_received=timezone.now(),
            )

            # Create related tests
            for ing_id in sample_data.get("selected_parameters", []):
                Test.objects.create(sample=sample, ingredient_id=ing_id)

            # Create payment
            Payment.objects.create(
                sample=sample,
                amount_due=sample_data.get("marking_label_fee", 0) + sum(
                    Ingredient.objects.filter(
                        id__in=sample_data["selected_parameters"]
                    ).values_list("price", flat=True)
                ),
                status="Pending",
            )

            saved_samples.append(sample)

        return Response(
            {"success": True, "message": "Sample submitted successfully. Awaiting Registrar approval."},
            status=status.HTTP_201_CREATED,
        )




# -------------------------------------------------------
# Authentication: login, logout, register, verify email
# -------------------------------------------------------
@api_view(['POST'])
@permission_classes([AllowAny])
def login_api(request):
    serializer = LoginSerializer(data=request.data, context={'request': request})
    serializer.is_valid(raise_exception=True)
    user = serializer.validated_data['user']
    refresh = RefreshToken.for_user(user)
    return Response({
        'success': True,
        'message': 'Login successful',
        'user': UserSerializer(user).data,
        'tokens': {'access': str(refresh.access_token), 'refresh': str(refresh)}
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def logout_api(request):
    try:
        refresh_token = request.data.get("refresh")
        token = RefreshToken(refresh_token)
        token.blacklist()
        return Response({'success': True, 'message': 'Logout successful'})
    except Exception:
        return Response({'success': False, 'message': 'Invalid token'}, status=400)


@api_view(['POST'])
@permission_classes([AllowAny])
def register_api(request):
    username = request.data.get('username')
    email = request.data.get('email')
    password = request.data.get('password')

    if not all([username, email, password]):
        return Response({'error': 'Username, email, and password are required.'}, status=400)

    if User.objects.filter(username=username).exists() or User.objects.filter(email=email).exists():
        return Response({'error': 'Username or email already exists.'}, status=400)

    user = User.objects.create_user(username=username, email=email, password=password, role='Customer')

    token = get_random_string(32)
    VerificationToken.objects.create(user=user, token=token, expires_at=timezone.now() + timedelta(days=1))

    verification_url = request.build_absolute_uri(reverse('verify-email', kwargs={'token': token}))
    subject = 'Verify Your Email for Lab System'
    message = f'Click below to verify your email:\n{verification_url}'
    send_mail(subject, message, 'no-reply@example.com', [email], fail_silently=True)

    return Response({'message': 'Registration successful. Please check your email for verification.'}, status=201)


@api_view(['GET'])
@permission_classes([AllowAny])
def verify_email_api(request, token):
    try:
        verification_token = VerificationToken.objects.get(token=token, expires_at__gt=timezone.now())
        user = verification_token.user
        user.is_verified = True
        user.save()
        verification_token.delete()
        return Response({'message': 'Email verified successfully. You can now log in.'})
    except VerificationToken.DoesNotExist:
        return Response({'error': 'Invalid or expired token.'}, status=400)


# -------------------------------------------------------
# Dashboards
# -------------------------------------------------------
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def admin_dashboard(request):
    if request.user.role != 'Admin':
        return Response({'success': False, 'message': 'Access denied. Admin role required.'}, status=403)
    return Response({
        'success': True,
        'stats': {
            'total_users': User.objects.count(),
            'total_departments': Department.objects.count(),
            'total_samples': Sample.objects.count(),
            'total_tests': Test.objects.count(),
        }
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def registrar_dashboard(request):
    if request.user.role != 'Registrar':
        return Response({'success': False, 'message': 'Access denied. Registrar role required.'}, status=403)
    my_samples = Sample.objects.filter(registrar=request.user)
    return Response({
        'success': True,
        'samples': SampleDashboardSerializer(my_samples, many=True).data
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def registrar_samples_api(request):
    """
    Return samples that need registrar action.
    - unclaimed samples: status='Awaiting Registrar Approval'
    - registrar’s claimed samples
    """
    if request.user.role != 'Registrar':
        return Response(
            {'success': False, 'message': 'Access denied. Registrar role required.'},
            status=status.HTTP_403_FORBIDDEN
        )

    # unclaimed samples
    unclaimed = Sample.objects.filter(
        status='Awaiting Registrar Approval', registrar__isnull=True
    ).order_by('-date_received')

    # registrar’s claimed samples
    my_samples = Sample.objects.filter(
        registrar=request.user
    ).order_by('-date_received')

    return Response({
        'success': True,
        'unclaimed_samples': SampleDashboardSerializer(unclaimed, many=True).data,
        'my_samples': SampleDashboardSerializer(my_samples, many=True).data,
    }, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def registrar_register_sample(request):
    """
    Registrar submits sample(s) on behalf of a customer directly to HOD.
    """
    if request.user.role != 'Registrar':
        return Response(
            {"success": False, "message": "Access denied. Registrar role required."},
            status=status.HTTP_403_FORBIDDEN
        )

    serializer = RegisterSampleSerializer(data=request.data, context={'request': request})
    if serializer.is_valid():
        samples = serializer.save()
        return Response({
            "success": True,
            "message": "Samples submitted to HOD successfully.",
            "samples": SampleDashboardSerializer(samples, many=True).data
        }, status=status.HTTP_201_CREATED)

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# api_views.py
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def registrar_submit_to_hod(request, sample_id):
    if request.user.role != 'Registrar':
        return Response({'success': False, 'message': 'Access denied. Registrar role required.'}, status=403)

    try:
        sample = Sample.objects.get(id=sample_id, registrar=request.user, status='Registrar Claimed')
        sample.status = 'Submitted to HOD'
        sample.date_submitted_to_hod = timezone.now()
        sample.save()
        return Response({
            'success': True,
            'message': f"Sample {sample.id} submitted to HOD successfully.",
            'sample': SampleDashboardSerializer(sample).data
        }, status=200)
    except Sample.DoesNotExist:
        return Response({'success': False, 'message': 'Sample not found or not claimed by this registrar.'}, status=404)





@api_view(['POST'])
@permission_classes([IsAuthenticated])
def registrar_claim_sample(request, sample_id):
    if request.user.role != 'Registrar':
        return Response(
            {'success': False, 'message': 'Access denied. Registrar role required.'},
            status=status.HTTP_403_FORBIDDEN
        )

    try:
        sample = Sample.objects.get(id=sample_id, status='Awaiting Registrar Approval', registrar__isnull=True)
        sample.registrar = request.user
        sample.status = 'Submitted to HOD'    # ✅ directly mark for HOD
        sample.date_submitted_to_hod = timezone.now()  # ✅ add timestamp if field exists
        sample.save()

        return Response({
            'success': True,
            'message': f"Sample {sample.id} claimed and submitted to HOD successfully.",
            'sample': SampleDashboardSerializer(sample).data
        }, status=status.HTTP_200_OK)

    except Sample.DoesNotExist:
        return Response(
            {'success': False, 'message': 'Sample not found or already claimed.'},
            status=status.HTTP_404_NOT_FOUND
        )

    return Response({"success": True, "message": "Sample successfully claimed."})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def unclaimed_samples(request):
    """
    Returns all samples that are not yet claimed by a Registrar.
    """
    samples = Sample.objects.filter(
        status='Awaiting Registrar Approval',   # ✅ ensures customer-submitted samples are shown
        registrar__isnull=True
    ).select_related('customer').prefetch_related('payment', 'test_set__ingredient')

    serializer = UnclaimedSampleSerializer(samples, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)






@api_view(['GET'])
@permission_classes([IsAuthenticated])
def hod_dashboard(request):
    """
    HOD views all submitted samples with full details.
    """
    if request.user.role != 'HOD':
        return Response({'success': False, 'message': 'Access denied. HOD role required.'}, status=403)

    samples = Sample.objects.filter(
        Q(status='Submitted to HOD') | Q(status='Awaiting HOD Review')
    ).select_related('customer').prefetch_related('test_set__ingredient')

    return Response({
        'success': True,
        'samples': FullSampleSerializer(samples, many=True).data
    }, status=200)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def hod_assign_technician(request, sample_id):
    """
    HOD assigns one or more technicians to specific tests in a sample.
    """
    if request.user.role != 'HOD':
        return Response({"success": False, "message": "Access denied. HOD role required."}, status=403)

    technician_ids = request.data.get("technician_ids", [])
    test_ids = request.data.get("test_ids", [])

    if not technician_ids or not test_ids:
        return Response({"success": False, "message": "Technicians and test IDs are required."}, status=400)

    try:
        sample = Sample.objects.get(id=sample_id)
    except Sample.DoesNotExist:
        return Response({"success": False, "message": "Sample not found."}, status=404)

    # Loop through each selected technician
    for tech_id in technician_ids:
        try:
            technician = User.objects.get(id=tech_id, role="Technician")
        except User.DoesNotExist:
            continue

        specialization = getattr(technician, "specialization", None)  # 👈 added field in User
        if not specialization:
            continue

        # Assign only tests that match technician's specialization
        tests = Test.objects.filter(
            id__in=test_ids,
            sample=sample,
            ingredient__test_type=specialization
        )

        for test in tests:
            test.assigned_to = technician
            test.status = "In Progress"
            test.save()

    sample.status = "In Progress"
    sample.save()

    return Response({
        "success": True,
        "message": "Technician(s) assigned successfully.",
        "sample": FullSampleSerializer(sample).data
    }, status=200)



@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_technicians(request):
    """
    Return all technicians, optionally filtered by specialization.
    Example: /api/technicians/?specialization=Chemistry
    """
    if request.user.role not in ['Admin', 'HOD']:
        return Response({"success": False, "message": "Access denied."}, status=403)

    specialization = request.GET.get("specialization")  # optional filter
    technicians = User.objects.filter(role="Technician")

    if specialization:
        technicians = technicians.filter(specialization=specialization)

    serializer = UserSerializer(technicians, many=True)
    return Response(serializer.data)







@api_view(['GET'])
@permission_classes([IsAuthenticated])
def technician_dashboard(request):
    if request.user.role != 'Technician':
        return Response({'success': False, 'message': 'Access denied. Technician role required.'}, status=403)

    assigned = Test.objects.filter(assigned_to=request.user)
    return Response({'success': True, 'tests': TechnicianDashboardSerializer(assigned, many=True).data})





@api_view(['GET'])
@permission_classes([IsAuthenticated])
def director_dashboard(request):
    if request.user.role != 'Director':
        return Response({'success': False, 'message': 'Access denied. Director role required.'}, status=403)
    return Response({'success': True, 'message': 'Director dashboard data here'})


# ViewSets
# -------------------------------------------------------
class SampleViewSet(viewsets.ModelViewSet):
    queryset = Sample.objects.all()
    serializer_class = SampleDashboardSerializer
    permission_classes = [IsAuthenticated]


class TestViewSet(viewsets.ModelViewSet):
    queryset = Test.objects.all()
    serializer_class = TestSerializer
    permission_classes = [IsAuthenticated]


class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]


class DepartmentViewSet(viewsets.ModelViewSet):
    queryset = Department.objects.all()
    serializer_class = DepartmentSerializer
    permission_classes = [IsAuthenticated]


class DivisionViewSet(viewsets.ModelViewSet):
    queryset = Division.objects.all()
    serializer_class = DivisionSerializer
    permission_classes = [IsAuthenticated]


class CustomerViewSet(viewsets.ModelViewSet):
    queryset = Customer.objects.all()
    serializer_class = CustomerSerializer
    permission_classes = [IsAuthenticated]


class PaymentViewSet(viewsets.ModelViewSet):
    queryset = Payment.objects.all()
    serializer_class = PaymentSerializer
    permission_classes = [IsAuthenticated]


class ResultViewSet(viewsets.ModelViewSet):
    queryset = Result.objects.all()
    serializer_class = ResultSerializer
    permission_classes = [IsAuthenticated]


class IngredientViewSet(viewsets.ModelViewSet):
    queryset = Ingredient.objects.all()
    serializer_class = IngredientSerializer
    permission_classes = [AllowAny]
