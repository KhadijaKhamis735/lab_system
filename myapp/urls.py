# myapp/urls.py

from django.urls import path, include
from rest_framework.routers import DefaultRouter

# The key change is here: Import the module itself, not individual functions.
from . import api_views

router = DefaultRouter()
router.register(r'users', api_views.UserViewSet)
router.register(r'departments', api_views.DepartmentViewSet)
router.register(r'divisions', api_views.DivisionViewSet)
router.register(r'customers', api_views.CustomerViewSet)
router.register(r'payments', api_views.PaymentViewSet)
router.register(r'results', api_views.ResultViewSet)
router.register(r'ingredients', api_views.IngredientViewSet)

urlpatterns = [
    # Router URLs
    path('', include(router.urls)),

    # Authentication and User-specific URLs
    path('auth/login/', api_views.login_api, name='api_login'),
    path('auth/logout/', api_views.logout_api, name='api_logout'),
    path('auth/profile/', api_views.user_profile, name='api_profile'),

    # Dashboard URLs
    path('dashboard/admin/', api_views.admin_dashboard, name='admin_dashboard'),
    path('dashboard/technician/', api_views.technician_dashboard, name='technician_dashboard'),
    path('dashboard/hod/', api_views.hod_dashboard, name='hod_dashboard'),
    path('dashboard/registrar/', api_views.registrar_dashboard, name='registrar_dashboard'),
    path('dashboard/director/', api_views.director_dashboard, name='director_dashboard'),

    # Sample & Test
    path('samples/', api_views.SampleListCreateAPI.as_view(), name='samples_api'),
    path('samples/<int:pk>/', api_views.SampleRetrieveUpdateDestroyAPI.as_view(), name='sample_detail_api'),
    path('tests/', api_views.TestListCreateAPI.as_view(), name='tests_api'),
    path('tests/<int:pk>/', api_views.TestRetrieveUpdateDestroyAPI.as_view(), name='test_detail_api'),
    path('submit-sample/', api_views.submit_sample_api, name='submit_sample'),

    # Payments
    path('payments/verify/<str:control_number>/', api_views.verify_payment_api, name='verify_payment'),

    # Placeholder URLs (if you uncomment them, make sure the views exist in api_views.py)
    # path('assign-to-hodv/<int:sample_id>/', api_views.assign_to_hodv_api, name='assign_to_hodv'),
    # path('assign-to-technician/<int:sample_id>/', api_views.assign_to_technician_api, name='assign_to_technician'),
    # path('department-activities/', api_views.department_activities, name='department_activities'),
    # path('pending-samples/', api_views.pending_samples, name='pending_samples'),
]