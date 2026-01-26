from django.contrib import admin
from django_object_actions import DjangoObjectActions, action
from bpmn_parser.models import Choreography
from django.utils.translation import gettext_lazy as _

class ChoreographyAdmin(DjangoObjectActions, admin.ModelAdmin):

    list_display = [ "name", "resource", "enabled", "has_details" ]
    search_fields = [ "name", "resource", ]
    list_filter = [ "enabled", ]

    change_actions = [ "action_enable", "action_disable", ]
    actions = [ "action_enable_all", "action_disable_all", ]

    @admin.display(boolean=True, description="Has details")
    def has_details(self, obj):
        return obj.details is not None and len(obj.details) > 0

    @action(label=_("Enable"), description=_("Enable the current choreography"))
    def action_enable(self, request, obj):
        if not obj.enabled:
            obj.enabled = True
            obj.save()

    @action(label=_("Disable"), description=_("Disable the current choreography"))
    def action_disable(self, request, obj):
        if obj.enabled:
            obj.enabled = False
            obj.save()


    @admin.action(description=_("Enable the selected choreographies"))
    def action_enable_all(self, request, queryset):
        for obj in queryset.all():
            self.action_enable(request, obj)


    @admin.action(description=_("Disable the selected choreographies"))
    def action_disable_all(self, request, queryset):
        for obj in queryset.all():
            self.action_disable(request, obj)

admin.site.register(Choreography, ChoreographyAdmin)
