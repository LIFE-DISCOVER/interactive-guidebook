from django.urls import path
from . import views

app_name = 'catalog'

urlpatterns = [
    path('', views.ServiceListView.as_view(), name='service_list'),
    path('guidebook/', views.GuidebookView.as_view(), name='guidebook'),
    path('guidebook/set-country/', views.SetCountryView.as_view(), name='set_country'),
    path('<slug:slug>/', views.ServiceDetailView.as_view(), name='service_detail'),
]
