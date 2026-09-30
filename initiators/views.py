from urllib.parse import quote

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.messages.views import SuccessMessageMixin
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext as _, gettext_lazy
from django.views.generic import (
    ListView, DetailView, CreateView, UpdateView, FormView, View,
)

from catalog.localization import localize_service_page, localize_services, service_translations

from .forms import (
    InitiatorForm,
    ProjectCreateForm,
    ProjectForm,
    ProjectPhaseChangeForm,
    ServiceApplicationForm,
    ServiceLinkCreateForm,
    ServiceLinkNoteForm,
)
from .models import Initiator, Project, ServiceApplication, ServiceLink


# ---------------------------------------------------------------------------
# Initiator views
# ---------------------------------------------------------------------------

class InitiatorListView(LoginRequiredMixin, ListView):
    model = Initiator
    template_name = 'initiators/initiator_list.html'
    context_object_name = 'initiators'
    ordering = ['last_name', 'first_name']
    paginate_by = 20


class InitiatorCreateView(LoginRequiredMixin, SuccessMessageMixin, CreateView):
    model = Initiator
    form_class = InitiatorForm
    template_name = 'initiators/initiator_form.html'
    success_message = gettext_lazy('Initiator %(first_name)s %(last_name)s was created.')

    def get_success_url(self):
        return reverse('initiators:initiator_detail', kwargs={'pk': self.object.pk})


class InitiatorDetailView(LoginRequiredMixin, DetailView):
    model = Initiator
    template_name = 'initiators/initiator_detail.html'
    context_object_name = 'initiator'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['projects'] = (
            self.object.projects
            .select_related('current_phase')
            .order_by('-created_at')
        )
        return ctx


class InitiatorUpdateView(LoginRequiredMixin, SuccessMessageMixin, UpdateView):
    model = Initiator
    form_class = InitiatorForm
    template_name = 'initiators/initiator_form.html'
    success_message = gettext_lazy('Changes to %(first_name)s %(last_name)s were saved.')

    def get_success_url(self):
        return reverse('initiators:initiator_detail', kwargs={'pk': self.object.pk})


# ---------------------------------------------------------------------------
# Project views
# ---------------------------------------------------------------------------

class ProjectListView(LoginRequiredMixin, ListView):
    model = Project
    template_name = 'initiators/project_list.html'
    context_object_name = 'projects'
    ordering = ['-created_at']
    paginate_by = 20

    def get_queryset(self):
        return super().get_queryset().select_related('initiator', 'current_phase')


class ProjectCreateView(LoginRequiredMixin, SuccessMessageMixin, CreateView):
    model = Project
    form_class = ProjectCreateForm
    template_name = 'initiators/project_form.html'
    success_message = gettext_lazy('Project "%(name)s" was created.')

    def get_initiator(self):
        return get_object_or_404(Initiator, pk=self.kwargs['pk'])

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['initiator'] = self.get_initiator()
        return ctx

    def form_valid(self, form):
        form.instance.initiator = self.get_initiator()
        return super().form_valid(form)

    def get_success_url(self):
        return reverse('projects:project_detail', kwargs={'pk': self.object.pk})


class ProjectDetailView(LoginRequiredMixin, DetailView):
    model = Project
    template_name = 'initiators/project_detail.html'
    context_object_name = 'project'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['phase_entries'] = self.object.phase_entries.select_related('phase')
        applications = list(
            self.object.service_applications
            .select_related('service', 'applied_by')
            .prefetch_related('links', service_translations('service__translations'))
            .order_by('-applied_on')
        )
        localize_services([sa.service for sa in applications])
        for sa in applications:
            links = list(sa.links.all())  # newest first
            sa.active_link = next((l for l in links if l.is_active and not l.is_used), None)
            sa.submitted_links = [l for l in links if l.is_used]
            sa.link_form = ServiceLinkCreateForm(auto_id=f'id_link_%s_{sa.pk}')
            if sa.active_link:
                sa.active_link.share_url = self.request.build_absolute_uri(sa.active_link.get_public_path())
                sa.active_link.mailto = self.build_mailto(sa, sa.active_link.share_url)
        ctx['service_applications'] = applications
        return ctx

    def build_mailto(self, sa, url):
        """Pre-filled email to the initiator; opens in the manager's own mail program."""
        initiator = self.object.initiator
        manager = self.request.user.get_full_name() or self.request.user.email
        subject = _('Information about "%(service)s" for your project "%(project)s"') % {
            'service': sa.service.text.name, 'project': self.object.name,
        }
        body = _(
            'Hello %(name)s,\n\n'
            'please open the following link to read about the service "%(service)s" '
            'and to send us your note:\n\n%(url)s\n\n'
            'Best regards,\n%(manager)s'
        ) % {'name': initiator.first_name, 'service': sa.service.text.name, 'url': url, 'manager': manager}
        return f'mailto:{quote(initiator.email)}?subject={quote(subject)}&body={quote(body)}'


class ProjectUpdateView(LoginRequiredMixin, SuccessMessageMixin, UpdateView):
    model = Project
    form_class = ProjectForm
    template_name = 'initiators/project_form.html'
    success_message = gettext_lazy('Changes to "%(name)s" were saved.')

    def get_success_url(self):
        return reverse('projects:project_detail', kwargs={'pk': self.object.pk})


class ProjectPhaseChangeView(LoginRequiredMixin, FormView):
    form_class = ProjectPhaseChangeForm
    template_name = 'initiators/project_phase_form.html'

    def get_project(self):
        return get_object_or_404(Project, pk=self.kwargs['pk'])

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['project'] = self.get_project()
        return ctx

    def get_initial(self):
        project = self.get_project()
        return {'current_phase': project.current_phase}

    def form_valid(self, form):
        project = self.get_project()
        new_phase = form.cleaned_data['current_phase']
        notes = form.cleaned_data.get('notes', '')
        if new_phase == project.current_phase:
            form.add_error(
                'current_phase',
                _('The project is already in the %(phase)s phase.') % {'phase': new_phase},
            )
            return self.form_invalid(form)
        project.current_phase = new_phase
        # update_fields triggers the signal to create a ProjectPhaseEntry
        project.save(update_fields=['current_phase', 'updated_at'])
        if notes:
            entry = project.phase_entries.first()
            if entry:
                entry.notes = notes
                entry.save(update_fields=['notes'])
        messages.success(self.request, _('Project moved to the %(phase)s phase.') % {'phase': new_phase})
        return redirect(reverse('projects:project_detail', kwargs={'pk': project.pk}))


# ---------------------------------------------------------------------------
# Service application views
# ---------------------------------------------------------------------------

class ServiceApplicationCreateView(LoginRequiredMixin, SuccessMessageMixin, CreateView):
    model = ServiceApplication
    form_class = ServiceApplicationForm
    template_name = 'initiators/service_application_form.html'
    success_message = gettext_lazy('Service "%(service)s" was added to the project.')

    def get_project(self):
        return get_object_or_404(Project, pk=self.kwargs['pk'])

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['project'] = self.get_project()
        kwargs['user'] = self.request.user
        return kwargs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['project'] = self.get_project()
        return ctx

    def form_valid(self, form):
        form.instance.project = self.get_project()
        form.instance.applied_by = self.request.user
        return super().form_valid(form)

    def get_success_url(self):
        return reverse('projects:project_detail', kwargs={'pk': self.object.project.pk})


class ServiceApplicationDeleteView(LoginRequiredMixin, View):
    def post(self, request, pk, sa_id):
        sa = get_object_or_404(ServiceApplication, pk=sa_id, project_id=pk)
        project_pk = sa.project_id
        service_name = sa.service.name
        sa.delete()
        messages.success(
            request, _('Service "%(service)s" was removed from the project.') % {'service': service_name},
        )
        return redirect(reverse('projects:project_detail', kwargs={'pk': project_pk}))

    def get(self, request, pk, sa_id):
        return redirect(reverse('projects:project_detail', kwargs={'pk': pk}))



# ---------------------------------------------------------------------------
# Service links: single-use links for initiators
# ---------------------------------------------------------------------------

def project_services_url(project_pk, sa_pk):
    return reverse('projects:project_detail', kwargs={'pk': project_pk}) + f'#service-{sa_pk}'


class ServiceLinkCreateView(LoginRequiredMixin, View):
    """Create a new link (with optional message); replaces an unused active one."""

    def post(self, request, pk, sa_id):
        sa = get_object_or_404(ServiceApplication.objects.select_related('service'), pk=sa_id, project_id=pk)
        form = ServiceLinkCreateForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                sa.links.filter(is_active=True, submitted_at__isnull=True).update(is_active=False)
                link = form.save(commit=False)
                link.application = sa
                link.created_by = request.user
                link.save()
            messages.success(
                request,
                _('Link for "%(service)s" created. Copy it or send it by email to the initiator.')
                % {'service': sa.service.name},
            )
        else:
            messages.error(request, ' '.join(form.errors.get('message', [])))
        return redirect(project_services_url(pk, sa.pk))

    def get(self, request, pk, sa_id):
        return redirect(project_services_url(pk, sa_id))


class ServiceLinkRevokeView(LoginRequiredMixin, View):
    def post(self, request, pk, sa_id, link_id):
        link = get_object_or_404(ServiceLink, pk=link_id, application_id=sa_id, application__project_id=pk)
        link.is_active = False
        link.save(update_fields=['is_active'])
        messages.success(request, _('The link was revoked and no longer works.'))
        return redirect(project_services_url(pk, sa_id))

    def get(self, request, pk, sa_id, link_id):
        return redirect(project_services_url(pk, sa_id))


class ServiceLinkView(View):
    """Public page behind a link: service info, the manager's message and a one-time note form."""

    template_name = 'initiators/service_link.html'

    def get_link(self, token):
        return get_object_or_404(
            ServiceLink.objects.select_related(
                'application__service__country', 'application__project', 'created_by',
            ).prefetch_related('application__service__translations'),
            token=token,
            is_active=True,
        )

    def render_page(self, request, link, form=None):
        if form is None and not link.is_used:
            form = ServiceLinkNoteForm()
        service = link.application.service
        text_languages = localize_service_page(service, request)
        response = render(request, self.template_name, {
            'link': link,
            'service': service,
            'text_languages': text_languages,
            'project': link.application.project,
            'official_link': service.official_link,
            'form': None if link.is_used else form,
        })
        # The token is a secret: keep the page out of search engines, caches and other
        # sites' referrer logs. ('no-referrer' would make browsers send "Origin: null" on
        # the note form, which fails Django's CSRF check; 'same-origin' keeps the URL
        # on this site only.)
        response['X-Robots-Tag'] = 'noindex, nofollow'
        response['Cache-Control'] = 'private, no-store'
        response['Referrer-Policy'] = 'same-origin'
        return response

    def get(self, request, token):
        return self.render_page(request, self.get_link(token))

    def post(self, request, token):
        link = self.get_link(token)
        if link.is_used:
            return self.render_page(request, link)
        form = ServiceLinkNoteForm(request.POST)
        if not form.is_valid():
            return self.render_page(request, link, form)
        # Conditional update: of two simultaneous submissions only one is saved.
        saved = ServiceLink.objects.filter(
            pk=link.pk, is_active=True, submitted_at__isnull=True,
        ).update(note=form.cleaned_data['note'], submitted_at=timezone.now())
        if saved:
            messages.success(request, _('Thank you! Your note has been sent.'))
        return redirect(request.get_full_path())
