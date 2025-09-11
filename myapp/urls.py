from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from . import api_views
from .api_views import unclaimed_samples

router = DefaultRouter()
router.register(r'users', api_views.UserViewSet)
router.register(r'departments', api_views.DepartmentViewSet)
router.register(r'divisions', api_views.DivisionViewSet)
router.register(r'customers', api_views.CustomerViewSet)
router.register(r'samples', api_views.SampleViewSet, basename='sample')
router.register(r'tests', api_views.TestViewSet, basename='test')
router.register(r'payments', api_views.PaymentViewSet)
router.register(r'results', api_views.ResultViewSet)
router.register(r'ingredients', api_views.IngredientViewSet)

urlpatterns = [
    # Authentication
    path('api/auth/login/', api_views.login_api, name='login'),
    path('api/auth/logout/', api_views.logout_api, name='logout'),
    path('api/auth/register/', api_views.register_api, name='register'),
    path('api/auth/verify-email/<str:token>/', api_views.verify_email_api, name='verify-email'),

    # Dashboards
    path('api/dashboard/admin/', api_views.admin_dashboard, name='admin_dashboard'),
    path('api/dashboard/registrar/', api_views.registrar_dashboard, name='registrar_dashboard'),
    path('api/dashboard/technician/', api_views.technician_dashboard, name='technician_dashboard'),
    path('api/dashboard/hod/', api_views.hod_dashboard, name='hod_dashboard'),
    path('api/dashboard/director/', api_views.director_dashboard, name='director_dashboard'),

    # Customer & Registrar workflows
    path('api/customer/submit-sample/', api_views.CustomerSubmitSampleAPIView.as_view(), name='customer_submit_sample'),
    path('api/registrar-samples/', api_views.registrar_samples_api, name='registrar_samples_api'),
    path('api/unclaimed-samples/', unclaimed_samples, name='unclaimed-samples'),
    path('api/registrar/register-sample/', api_views.registrar_register_sample, name='registrar_register_sample'),
    path("api/technicians/", api_views.list_technicians, name="list_technicians"),



    # Registrar → HOD
    path('api/registrar/submit-to-hod/<int:sample_id>/', api_views.registrar_submit_to_hod, name='registrar_submit_to_hod'),
    path('api/claim-sample/<int:sample_id>/', api_views.registrar_claim_sample, name='registrar_claim_sample'),
    path("api/hod/assign-technician/<int:sample_id>/", api_views.hod_assign_technician, name="hod_assign_technician"),


    # HOD
    path('api/hod/samples/', api_views.hod_dashboard, name='hod_dashboard'),


    # JWT
    path('api/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),

    # DRF router
    path('api/', include(router.urls)),
]
