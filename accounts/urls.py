from django.urls import path
from django.contrib.auth import views as auth_views

from .views import GuidebookLoginView, SetupView

app_name = 'accounts'

urlpatterns = [
    path('login/', GuidebookLoginView.as_view(), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('setup/', SetupView.as_view(), name='setup'),
]
