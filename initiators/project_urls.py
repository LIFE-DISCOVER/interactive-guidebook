from django.urls import path
from . import views

app_name = 'projects'

urlpatterns = [
    path('', views.ProjectListView.as_view(), name='project_list'),
    path('<int:pk>/', views.ProjectDetailView.as_view(), name='project_detail'),
    path('<int:pk>/edit/', views.ProjectUpdateView.as_view(), name='project_update'),
    path('<int:pk>/phase/', views.ProjectPhaseChangeView.as_view(), name='project_phase_change'),
    path('<int:pk>/services/add/', views.ServiceApplicationCreateView.as_view(), name='service_application_create'),
    path('<int:pk>/services/<int:sa_id>/delete/', views.ServiceApplicationDeleteView.as_view(), name='service_application_delete'),
    path('<int:pk>/services/<int:sa_id>/link/', views.ServiceLinkCreateView.as_view(), name='service_link_create'),
    path(
        '<int:pk>/services/<int:sa_id>/link/<int:link_id>/revoke/',
        views.ServiceLinkRevokeView.as_view(),
        name='service_link_revoke',
    ),
]
