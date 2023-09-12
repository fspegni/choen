from django.contrib import admin

# Register your models here.

from engine.models import RunningInstance

class RunningInstanceAdmin(admin.ModelAdmin):

    list_display = [ "id", "label", "engine_type", "choreography", ]
    list_filter = [ "engine_type", ]
    search_fields = [ "id", "label", "choreography__name", "choreography__resource" ]


admin.site.register(RunningInstance, RunningInstanceAdmin)
