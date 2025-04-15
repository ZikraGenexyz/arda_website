from django.urls import path, include
from . import views


urlpatterns = [
    # path('', views.home, name='home'),
    path('direct_overlay/', views.direct_overlay, name='direct_overlay'),
    path('', views.direct_page, name='direct_page'),
    path('apis/v1', include('apis.urls')),
]
