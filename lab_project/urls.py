"""
URL configuration for lab_project project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
# lab_project/lab_project/urls.py

from django.contrib import admin
from django.urls import path, include

# No longer need this import, as we're including the app's urls.
# from myapp import views

# lab_project/lab_project/urls.py

# lab_project/lab_project/urls.py

from django.contrib import admin
from django.urls import path, include
from django.http import JsonResponse

# This is a simple view function for the root URL
def api_root_view(request):
    return JsonResponse({
        "message": "Welcome to the Lab Management System API!",
        "api_endpoints": "/api/",
        "admin_dashboard": "/admin/"
    })

urlpatterns = [
    # New pattern to handle the root URL
    path('', api_root_view),
    
    path('admin/', admin.site.urls),
    path('api/', include('myapp.urls')),
]