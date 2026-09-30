from django.contrib import admin

from .models import Initiator, Project, ProjectPhaseEntry, ServiceApplication, ServiceLink


@admin.register(Initiator)
class InitiatorAdmin(admin.ModelAdmin):
    list_display = ('full_name', 'email', 'organization')
    search_fields = ('first_name', 'last_name', 'email', 'organization')


class ProjectPhaseEntryInline(admin.TabularInline):
    model = ProjectPhaseEntry
    extra = 0
    readonly_fields = ('phase', 'entered_on')
    can_delete = False


class ServiceApplicationInline(admin.TabularInline):
    model = ServiceApplication
    extra = 0


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ('name', 'initiator', 'current_phase', 'status')
    list_filter = ('status', 'current_phase')
    inlines = [ProjectPhaseEntryInline, ServiceApplicationInline]


@admin.register(ServiceLink)
class ServiceLinkAdmin(admin.ModelAdmin):
    list_display = ('application', 'created_by', 'created_at', 'submitted_at', 'is_active')
    list_filter = ('is_active',)
    readonly_fields = ('token', 'created_at', 'submitted_at')
    search_fields = ('application__project__name', 'application__service__name')
