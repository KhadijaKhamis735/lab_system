from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views  # Changed from api_views to views

router = DefaultRouter()
router.register(r'users', views.UserViewSet)
router.register(r'departments', views.DepartmentViewSet)
router.register(r'divisions', views.DivisionViewSet)
router.register(r'customers', views.CustomerViewSet)
router.register(r'payments', views.PaymentViewSet)
router.register(r'results', views.ResultViewSet)

urlpatterns = [
    # Authentication & profile
    path('auth/login/', views.login_api, name='api_login'),
    path('auth/logout/', views.logout_api, name='api_logout'),
    path('auth/profile/', views.user_profile, name='api_profile'),

    # Dashboards
    path('dashboard/technician/', views.technician_dashboard, name='technician_dashboard'),
    path('dashboard/hod/', views.hod_dashboard, name='hod_dashboard'),
    path('dashboard/registrar/', views.registrar_dashboard, name='registrar_dashboard'),
    path('dashboard/director/', views.director_dashboard, name='director_dashboard'),

    # Samples & Tests
    path('samples/', views.SampleListCreateAPI.as_view(), name='samples_api'),
    path('samples/<int:pk>/', views.SampleRetrieveUpdateDestroyAPI.as_view(), name='sample_detail_api'),
    path('tests/', views.TestListCreateAPI.as_view(), name='tests_api'),
    path('tests/<int:pk>/', views.TestRetrieveUpdateDestroyAPI.as_view(), name='test_detail_api'),

    # Custom Registrar Endpoints
    path('register-sample/', views.register_sample_api, name='register_sample'),
    path('payments/verify/<str:control_number>/', views.verify_payment_api, name='verify_payment'),

    # router (other CRUD)
    path('', include(router.urls)),
]