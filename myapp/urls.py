from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from . import api_views
from .api_views import (
    # Auth
    login_api, logout_api, register_api, verify_email_api,
    forgot_password_api, reset_password_api,
    get_current_user,
    # Dashboards
    admin_dashboard, registrar_dashboard, technician_dashboard,
    hod_dashboard, dg_dashboard,
    # Registrar workflows
    registrar_samples_api, registrar_register_sample,
    registrar_submit_to_hod, registrar_claim_sample, unclaimed_samples,
    # HOD workflows
    hod_assign_technician, list_technicians,
    hod_accept_result, hod_reject_result,
    submit_to_director,
    # Technician workflows
    CustomerSubmitSampleAPIView, technician_submit_result,
    # ViewSets
    UserViewSet, DepartmentViewSet, DivisionViewSet,
    CustomerViewSet, SampleViewSet, TestViewSet,
    PaymentViewSet, ResultViewSet, IngredientViewSet,
)

router = DefaultRouter()
router.register(r'users', UserViewSet)
router.register(r'departments', DepartmentViewSet)
router.register(r'divisions', DivisionViewSet)
router.register(r'customers', CustomerViewSet)
router.register(r'samples', SampleViewSet, basename='sample')
router.register(r'tests', TestViewSet, basename='test')
router.register(r'payments', PaymentViewSet)
router.register(r'results', ResultViewSet)
router.register(r'ingredients', IngredientViewSet)

urlpatterns = [
    # Authentication
    path('api/auth/login/', login_api, name='login'),
    path('api/auth/logout/', logout_api, name='logout'),
    path('api/auth/register/', register_api, name='register'),
    path('api/auth/verify-email/<str:token>/', verify_email_api, name='verify-email'),
    path('api/auth/forgot-password/', forgot_password_api, name='forgot-password'),
    path('api/auth/reset-password/<str:token>/', reset_password_api, name='reset-password'),
    path('api/users/me/', get_current_user, name='current-user'),
    # Dashboards
    path('api/dashboard/admin/', admin_dashboard, name='admin_dashboard'),
    path('api/dashboard/registrar/', registrar_dashboard, name='registrar_dashboard'),
    path('api/dashboard/technician/', technician_dashboard, name='technician_dashboard'),
    path('api/dashboard/hod/', hod_dashboard, name='hod_dashboard'),
    path('api/dashboard/dg/', dg_dashboard, name='dg-dashboard'),
    # Customer & Registrar workflows
    path('api/customer/submit-sample/', CustomerSubmitSampleAPIView.as_view(), name='customer_submit_sample'),
    path('api/registrar-samples/', registrar_samples_api, name='registrar_samples_api'),
    path('api/unclaimed-samples/', unclaimed_samples, name='unclaimed_samples'),
    path('api/registrar/register-sample/', registrar_register_sample, name='registrar_register_sample'),
    path('api/registrar/submit-to-hod/<int:sample_id>/', registrar_submit_to_hod, name='registrar_submit_to_hod'),
    path('api/claim-sample/<int:sample_id>/', registrar_claim_sample, name='registrar_claim_sample'),
    # HOD workflows
    path('api/hod/assign-technician/<int:sample_id>/', hod_assign_technician, name='hod_assign_technician'),
    path('api/technicians/', list_technicians, name='list_technicians'),
    path('api/hod/accept-result/<int:test_id>/', hod_accept_result, name='hod-accept-result'),
    path('api/hod/reject-result/<int:test_id>/', hod_reject_result, name='hod-reject-result'),
    path('api/submit-to-director/<int:test_id>/', submit_to_director, name='submit-to-director'),
    # Technician workflows
    path('api/technician/submit-result/<int:test_id>/', technician_submit_result, name='technician_submit_result'),
    # JWT Authentication
    path('api/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('api/dg/approve-result/<int:test_id>/', api_views.dg_approve_result, name='dg_approve_result'),

    # HOD → Director
path("api/hod/submit-to-director/<int:sample_id>/", api_views.hod_submit_to_director, name="hod_submit_to_director"),

    # DRF router
    path('api/', include(router.urls)),
]