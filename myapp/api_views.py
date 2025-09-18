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
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from django.conf import settings
from rest_framework.permissions import IsAuthenticated




from .models import (
    User, Department, Division, Customer, Sample, Test, Payment, Result, Ingredient, VerificationToken
)
from .serializers import (
    LoginSerializer, UserSerializer, DepartmentSerializer, DivisionSerializer,
    CustomerSerializer, SampleDashboardSerializer, TestSerializer, PaymentSerializer, ResultSerializer,
    IngredientSerializer, RegisterSampleSerializer, CreateUserSerializer, UnclaimedSampleSerializer,
    FullSampleSerializer, TechnicianDashboardSerializer,    # ✅ add this import
)

logger = logging.getLogger(__name__)


class IsAdmin(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == 'Admin'
    

    # Add get_current_user view
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_current_user(request):
    serializer = UserSerializer(request.user)
    return Response(serializer.data)


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

        # Clean invalid fields
        customer_data.pop("submission_date", None)
        customer_data.pop("submission_time", None)

        email = customer_data.get("email")
        phone = customer_data.get("phone_number")

        # Try to find customer by email or phone
        customer = None
        if email:
            customer = Customer.objects.filter(email=email).first()
        if not customer and phone:
            customer = Customer.objects.filter(phone_number=phone).first()

        # If not found, create new
        if not customer:
            customer = Customer.objects.create(**customer_data)
        else:
            # Update existing customer details
            for field, value in customer_data.items():
                if value not in [None, ""]:
                    setattr(customer, field, value)
            customer.save()

        saved_samples = []
        for sample_data in samples_data:
            sample = Sample.objects.create(
                customer=customer,
                sample_name=sample_data.get("name", ""),
                sample_details=sample_data.get("sample_details", ""),
                status="Awaiting Registrar Approval",
                date_received=timezone.now()
            )

            # Related tests
            for ing_id in sample_data.get("selected_parameters", []):
                Test.objects.create(sample=sample, ingredient_id=ing_id)

            # Payment
            Payment.objects.create(
                sample=sample,
                amount_due=sample_data.get("marking_label_fee", 0) + sum(
                    Ingredient.objects.filter(id__in=sample_data.get("selected_parameters", []))
                    .values_list("price", flat=True)
                ),
                status="Pending",
            )

            saved_samples.append(sample)

        return Response(
            {"success": True, "message": "Sample submitted successfully. Awaiting Registrar approval."},
            status=status.HTTP_201_CREATED
        )
    


# ------------------- Forgot Password -------------------
@api_view(['POST'])
@permission_classes([AllowAny])
def forgot_password_api(request):
    email = request.data.get("email")
    if not email:
        return Response({"error": "Email is required"}, status=400)

    try:
        user = User.objects.get(email=email)
    except User.DoesNotExist:
        return Response({"error": "No account found with this email"}, status=404)

    # Generate reset token
    token = get_random_string(50)
    VerificationToken.objects.create(
        user=user,
        token=token,
        expires_at=timezone.now() + timedelta(hours=1)  # token valid for 1 hour
    )

    reset_url = request.build_absolute_uri(
        reverse("reset-password", kwargs={"token": token})
    )

    subject = "Reset Your Password - Zafiri Lab"
    message = f"Hello {user.username},\n\nClick the link below to reset your password:\n{reset_url}\n\nIf you didn’t request this, please ignore."
    send_mail(
        subject,
        message,
        settings.EMAIL_HOST_USER,   # ✅ send using configured Gmail
        [email],
        fail_silently=False,
    )

    return Response({"message": "Password reset instructions sent to your email."}, status=200)


# ------------------- Reset Password -------------------
@api_view(['POST'])
@permission_classes([AllowAny])
def reset_password_api(request, token):
    new_password = request.data.get("password")
    if not new_password:
        return Response({"error": "Password is required"}, status=400)

    try:
        reset_token = VerificationToken.objects.get(token=token, expires_at__gt=timezone.now())
    except VerificationToken.DoesNotExist:
        return Response({"error": "Invalid or expired token"}, status=400)

    user = reset_token.user
    user.password = make_password(new_password)
    user.save()

    # Remove token so it cannot be reused
    reset_token.delete()

    # Send confirmation email
    subject = "Your Password Has Been Reset"
    message = f"Hello {user.username},\n\nYour password was successfully reset. If this wasn’t you, please contact support immediately."
    send_mail(
        subject,
        message,
        settings.EMAIL_HOST_USER,
        [user.email],
        fail_silently=False,
    )

    return Response({"message": "Password reset successfully. You can now log in."}, status=200)





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
        sample = Sample.objects.get(
            id=sample_id,
            status='Awaiting Registrar Approval',
            registrar__isnull=True
        )
        sample.registrar = request.user
        sample.status = 'Registrar Claimed'   # 👈 FIXED (was "Submitted to HOD")
        sample.save()

        return Response({
            'success': True,
            'message': f"Sample {sample.id} claimed successfully. Now waiting to be submitted to HOD.",
            'sample': SampleDashboardSerializer(sample).data
        }, status=status.HTTP_200_OK)

    except Sample.DoesNotExist:
        return Response(
            {'success': False, 'message': 'Sample not found or already claimed.'},
            status=status.HTTP_404_NOT_FOUND
        )





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






@api_view(["GET"])
@permission_classes([IsAuthenticated])
def hod_dashboard(request):
    """
    Head of Department dashboard – view all samples submitted by registrar.
    Shows only samples with status 'Submitted to HOD' or 'Awaiting HOD Review'.
    """
    samples = (
        Sample.objects.filter(
            Q(status__iexact="Submitted to HOD") |
            Q(status__iexact="Awaiting HOD Review")
        )
        .select_related("customer")
        .prefetch_related("test_set__ingredient")
    )

    serializer = FullSampleSerializer(samples, many=True)
    return Response(serializer.data)  


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



# api_views.py
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def technician_submit_result(request, test_id):
    """
    Technician submits test results -> moves to HOD review if all tests done.
    """
    if request.user.role != 'Technician':
        return Response(
            {"success": False, "message": "Access denied. Technician role required."},
            status=status.HTTP_403_FORBIDDEN
        )

    try:
        test = Test.objects.get(id=test_id, assigned_to=request.user)
    except Test.DoesNotExist:
        return Response(
            {"success": False, "message": "Test not found or not assigned to you."},
            status=status.HTTP_404_NOT_FOUND
        )

    results = request.data.get("results")
    if not results:
        return Response(
            {"success": False, "message": "Results are required."},
            status=status.HTTP_400_BAD_REQUEST
        )

    # Save test result
    test.results = results
    test.status = "Awaiting HOD Review"
    test.submitted_date = timezone.now()
    test.save()

    # Check if all tests for the sample are submitted
    sample = test.sample
    all_submitted = sample.test_set.filter(
        status__in=["Pending", "In Progress"]
    ).count() == 0

    if all_submitted:
        sample.status = "Awaiting HOD Review"
        sample.save()

    return Response({
        "success": True,
        "message": f"Results for test {test.id} submitted to HOD successfully.",
        "sample": FullSampleSerializer(sample).data  # ✅ includes customer info & contact
    }, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def hod_submit_to_director(request, sample_id):
    """
    HOD submits reviewed test results to Director.
    """
    if request.user.role != 'HOD':
        return Response(
            {"success": False, "message": "Access denied. HOD role required."},
            status=status.HTTP_403_FORBIDDEN
        )

    try:
        sample = Sample.objects.get(id=sample_id, status="Awaiting HOD Review")
    except Sample.DoesNotExist:
        return Response(
            {"success": False, "message": "Sample not found or not ready for submission."},
            status=status.HTTP_404_NOT_FOUND
        )

    sample.status = "Submitted to Director"
    sample.date_submitted_to_director = timezone.now()
    sample.save()

    return Response({
        "success": True,
        "message": f"Sample {sample.id} submitted to Director successfully.",
        "sample": FullSampleSerializer(sample).data
    }, status=status.HTTP_200_OK)



@api_view(['GET'])
@permission_classes([IsAuthenticated])
def dg_dashboard(request):
    if request.user.role != 'Director':
        return Response({"success": False, "message": "Access denied. Director role required."}, status=403)
    try:
        samples = Sample.objects.prefetch_related('test_set').filter(test_set__status="Awaiting DG Review").distinct()
        serializer = FullSampleSerializer(samples, many=True)
        return Response(serializer.data, status=200)
    except Exception as e:
        return Response({"success": False, "message": str(e)}, status=500)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def dg_approve_result(request, test_id):
    if request.user.role not in ['Director', 'Director General']:
        return Response(
            {"success": False, "message": "Access denied. Director role required."},
            status=403
        )

    try:
        test = Test.objects.get(id=test_id, status="Awaiting DG Review")
        test.status = "Approved"
        test.approved_by = request.user
        test.approved_date = timezone.now()
        test.save()
        return Response(
            {"success": True, "message": "Test approved by Director."},
            status=200
        )
    except Test.DoesNotExist:
        return Response(
            {"success": False, "message": "Test not found or not awaiting DG review."},
            status=404
        )
 # Fixed: Removed extra )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def hod_reject_result(request, test_id):
    if request.user.role != 'HOD':
        return Response({"success": False, "message": "Access denied. HOD role required."}, status=403)
    try:
        test = Test.objects.get(id=test_id, status="Awaiting HOD Review")
        reassigned_to_id = request.data.get("reassigned_to")
        if not reassigned_to_id:
            return Response({"success": False, "message": "Technician ID required for reassignment."}, status=400)
        try:
            technician = User.objects.get(id=reassigned_to_id, role="Technician", specialization=test.ingredient.test_type)
        except User.DoesNotExist:
            return Response({"success": False, "message": "Invalid technician or specialization mismatch."}, status=400)
        test.status = "Pending"
        test.assigned_to = technician
        test.save()
        return Response({"success": True, "message": "Test rejected and reassigned successfully."}, status=200)
    except Test.DoesNotExist:
        return Response({"success": False, "message": "Test not found or not awaiting HOD review."}, status=404)
    

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def hod_accept_result(request, test_id):
    if request.user.role != 'HOD':
        return Response({"success": False, "message": "Access denied. HOD role required."}, status=403)
    try:
        test = Test.objects.get(id=test_id, status="Awaiting HOD Review")
        test.status = "Awaiting DG Review"
        test.approved_by = request.user
        test.approved_date = timezone.now()
        test.save()
        return Response({"success": True, "message": "Test approved and submitted to Director."}, status=200)
    except Test.DoesNotExist:
        return Response({"success": False, "message": "Test not found or not awaiting HOD review."}, status=404)
    




# Existing views (e.g., hod_dashboard, hod_accept_result, hod_reject_result, get_technicians)
# Add these new views for DG dashboard

# Remove the second instance of dg_dashboard and dg_approve_result
# Keep only one instance, and add dg_reject_result for completeness

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def dg_dashboard(request):
    if request.user.role != 'Director General':
        return Response({"success": False, "message": "Access denied. Director role required."}, status=403)
    try:
        samples = Sample.objects.prefetch_related('test_set').filter(test_set__status="Awaiting DG Review").distinct()
        serializer = FullSampleSerializer(samples, many=True)
        return Response(serializer.data, status=200)
    except Exception as e:
        return Response({"success": False, "message": str(e)}, status=500)




@api_view(['POST'])
@permission_classes([IsAuthenticated])
def submit_to_director(request, test_id):
    if request.user.role != 'HOD':
        return Response({"success": False, "message": "Access denied. HOD role required."}, status=403)
    try:
        test = Test.objects.get(id=test_id, status="Awaiting HOD Review")
        test.status = "Awaiting DG Review"
        test.approved_by = request.user
        test.approved_date = timezone.now()
        test.save()
        return Response({"success": True, "message": "Test submitted to Director successfully."}, status=200)
    except Test.DoesNotExist:
        return Response({"success": False, "message": "Test not found or not awaiting HOD review."}, status=404)
    


    


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
