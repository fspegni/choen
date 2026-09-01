"""bpmn2solidity URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/3.2/topics/http/urls/
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
from django.contrib import admin
from django.urls import path, include
from django.conf.urls.static import static
from django.views.generic import TemplateView
from django.shortcuts import render, redirect

from django.conf import settings

from rest_framework import routers, serializers, viewsets
from rest_framework.authtoken import views

from bpmn_parser.api import ChoreographyViewSet
from mpst.api import MPSTViewSet
from engine.api import RunningInstanceViewSet
from bpmn2solidity.api import ChoenAuthToken #choen_login
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth import authenticate, login
from django.contrib import messages

class HomeView(LoginRequiredMixin, TemplateView):

    template_name = "index.html"

def loginview(request):
    if request.method == 'POST':
        user = authenticate(request, username=request.POST["username"],
                            password=request.POST["password"])
        if user:
            login(request, user)
            messages.success(request, 'Logged in successfully')
            return redirect('home')
        else:
            messages.error(request, 'Logged in Fail')
    return render(request, 'login.html')


router = routers.DefaultRouter()
router.register(r'choreographies', ChoreographyViewSet)
router.register(r'mpst', MPSTViewSet)
router.register(r'runninginstances', RunningInstanceViewSet)


urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include(router.urls)),
    path('api/auth/', include('rest_framework.urls', namespace='rest_framework')),
    path('api/login/', ChoenAuthToken.as_view()),
#    path('api/login/', views.obtain_auth_token),
    path('login/', loginview, name='login'),
    path('', HomeView.as_view(), name="home"),
] + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT) + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT) 

