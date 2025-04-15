from django.urls import path, include
from . import views


urlpatterns = [
    path('', views.home, name='home'),
    path('download/', views.download, name='download'),
    path('start_process/', views.start_process, name='start_process'),
    path('get_progress/', views.get_progress, name='get_progress'),
    path('apis/v1', include('apis.urls')),
]
