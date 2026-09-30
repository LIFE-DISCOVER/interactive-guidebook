from django.urls import path
from . import views

app_name = 'initiators'

urlpatterns = [
    path('', views.InitiatorListView.as_view(), name='initiator_list'),
    path('new/', views.InitiatorCreateView.as_view(), name='initiator_create'),
    path('<int:pk>/', views.InitiatorDetailView.as_view(), name='initiator_detail'),
    path('<int:pk>/edit/', views.InitiatorUpdateView.as_view(), name='initiator_update'),
    path('<int:pk>/projects/new/', views.ProjectCreateView.as_view(), name='project_create'),
]
