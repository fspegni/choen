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

from django.conf import settings

from rest_framework import routers, serializers, viewsets
from rest_framework.authtoken import views

from bpmn_parser.api import ChoreographyViewSet
from engine.api import RunningInstanceViewSet
from bpmn2solidity.api import ChoenAuthToken #choen_login

class HomeView(TemplateView):

    template_name = "index.html"

router = routers.DefaultRouter()
router.register(r'choreographies', ChoreographyViewSet)
router.register(r'runninginstances', RunningInstanceViewSet)

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include(router.urls)),
    path('api/auth/', include('rest_framework.urls', namespace='rest_framework')),
    path('api/login/', ChoenAuthToken.as_view()),
#    path('api/login/', views.obtain_auth_token),
    path('', HomeView.as_view()),

] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT) + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

