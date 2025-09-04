from django.urls import path, include
from rest_framework.routers import DefaultRouter

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
    path('', include(router.urls)),
    path('auth/login/', api_views.login_api, name='api_login'),
    path('auth/logout/', api_views.logout_api, name='api_logout'),
    path('auth/profile/', api_views.user_profile, name='api_profile'),
    path('dashboard/admin/', api_views.admin_dashboard, name='admin_dashboard'),
    path('dashboard/technician/', api_views.technician_dashboard, name='technician_dashboard'),
    path('dashboard/hod/', api_views.hod_dashboard, name='hod_dashboard'),
    path('dashboard/registrar/', api_views.registrar_dashboard, name='registrar_dashboard'),
    path('dashboard/director/', api_views.director_dashboard, name='director_dashboard'),
    path('samples/', api_views.SampleListCreateAPI.as_view(), name='samples_api'),
    path('samples/<int:pk>/', api_views.SampleRetrieveUpdateDestroyAPI.as_view(), name='sample_detail_api'),
    path('tests/', api_views.TestListCreateAPI.as_view(), name='tests_api'),
    path('tests/<int:pk>/', api_views.TestRetrieveUpdateDestroyAPI.as_view(), name='test_detail_api'),
    path('submit-sample/', api_views.submit_sample_api, name='submit_sample'),
    path('payments/verify/<str:control_number>/', api_views.verify_payment_api, name='verify_payment'),
    path('registrar-samples/', api_views.registrar_samples_api, name='registrar_samples'),
    path('admin/add-user/', api_views.admin_add_user, name='admin_add_user'),
    path('technician-assigned-tests/', api_views.technician_assigned_tests, name='technician_assigned_tests'),
    path('assign-technician-to-sample/', api_views.assign_technician_to_sample, name='assign_technician_to_sample'),
]