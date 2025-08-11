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

urlpatterns = [
    # Authentication & profile
    path('auth/login/', api_views.login_api, name='api_login'),
    path('auth/logout/', api_views.logout_api, name='api_logout'),
    path('auth/profile/', api_views.user_profile, name='api_profile'),

    # Dashboards
    path('dashboard/technician/', api_views.technician_dashboard, name='technician_dashboard'),
    path('dashboard/hod/', api_views.hod_dashboard, name='hod_dashboard'),
    path('dashboard/registrar/', api_views.registrar_dashboard, name='registrar_dashboard'),
    path('dashboard/director/', api_views.director_dashboard, name='director_dashboard'),

    # Samples & Tests
    path('samples/', api_views.SampleListCreateAPI.as_view(), name='samples_api'),
    path('samples/<int:pk>/', api_views.SampleRetrieveUpdateDestroyAPI.as_view(), name='sample_detail_api'),
    path('tests/', api_views.TestListCreateAPI.as_view(), name='tests_api'),
    path('tests/<int:pk>/', api_views.TestRetrieveUpdateDestroyAPI.as_view(), name='test_detail_api'),

    # router (other CRUD)
    path('', include(router.urls)),
]
