from django.contrib import admin
from django.urls import path, include
from django.http import JsonResponse

def api_root_view(request):
    return JsonResponse({
        "message": "Welcome to the Lab Management System API!",
        "api_endpoints": "/api/",
        "admin_dashboard": "/admin/"
    })

urlpatterns = [
    path('', api_root_view),
    path('admin/', admin.site.urls),
    path('', include('myapp.urls')),  # Includes both manual paths and router URLs
]