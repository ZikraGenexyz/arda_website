from django.urls import path, include
from . import views


urlpatterns = [
    path('', views.home, name='home'),
    path('apis/v1', include('apis.urls')),
]
