from django.urls import path, include
from . import views


urlpatterns = [
    path('', views.home, name='home'),
    path('progress/', views.get_progress, name='get_progress'),
    path('apis/v1', include('apis.urls')),
]
