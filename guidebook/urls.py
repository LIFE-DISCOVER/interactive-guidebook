from django.conf.urls.i18n import i18n_patterns
from django.contrib import admin
from django.urls import path, include
from django.views.generic import TemplateView

from accounts.views import switch_language
from initiators.views import ServiceLinkView

urlpatterns = [
    # Outside the language prefix: it moves the visitor between prefixes.
    path('language/<str:language>/', switch_language, name='switch_language'),
]

urlpatterns += i18n_patterns(
    path('', TemplateView.as_view(template_name='home.html'), name='home'),
    path('admin/', admin.site.urls),
    path('accounts/', include('accounts.urls', namespace='accounts')),
    path('catalog/', include('catalog.urls', namespace='catalog')),
    path('initiators/', include('initiators.urls', namespace='initiators')),
    path('projects/', include('initiators.project_urls', namespace='projects')),
    # Public, single-use links for initiators (no login).
    path('share/<str:token>/', ServiceLinkView.as_view(), name='service_link'),
)
