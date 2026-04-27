from django.urls import path
from . import views

urlpatterns = [
    # Page views
    path('', views.list_view, name='list_view'),
    path('export', views.export_view, name='export_view'),
    path('geoalign/<int:pk>/', views.alignment_view, name='alignment_view'),

    # API endpoints
    path('api/data/<int:pk>/', views.point_cloud_data_api, name='api_data'),
    path('api/save/<int:pk>/', views.save_transform_api, name='api_save'),
]