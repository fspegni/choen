from django.contrib import admin

from bpmn_parser.models import Choreography

class ChoreographyAdmin(admin.ModelAdmin):

    list_display = [ "name", "resource", ]
    search_fields = [ "name", "resource", ]


admin.site.register(Choreography, ChoreographyAdmin)
