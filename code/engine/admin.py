from django.contrib import admin
from django.utils.html import format_html

# Register your models here.

from engine.models import RunningInstance

class RunningInstanceAdmin(admin.ModelAdmin):

    list_display = [ "id", "label", "engine_type", "choreography", "running", ]
    list_filter = [ "engine_type", "running", ]
    search_fields = [ "id", "label", "choreography__name", "choreography__resource" ]

    fields = [ "label", "engine_type", "choreography", "running", "rei", "automaton", "enforcer_states", "enforcer_buffer", ]

    readonly_fields = [ "rei", "automaton", "enforcer_states",  "enforcer_buffer", ]

    def rei(self, obj : RunningInstance):
        return format_html("<pre>{}</pre>", str(obj.rei))

    def automaton(self, obj : RunningInstance):
        
        transitions = []
        for t in obj.nfa.transitions:
            #print(f"* {t}")
            t_repr = str(t)
            #print(f"+ {t_repr}")
            #print(obj.enforcer.engine)
            if obj.enforcer.engine.is_state_current(t.source):
                t_repr = f" * {t_repr}"
            else:
                t_repr = f"   {t_repr}"
            transitions.append(t_repr)

        return format_html("<pre>{}</pre>", str(obj.nfa) + "\n\nTransitions (*=enabled)" + "\n\n" + "\n".join(transitions))

    def enforcer_states(self, obj : RunningInstance):
        print(obj.enforcer)
        return format_html("<pre>{}</pre>", ", ".join(obj.enforcer.engine.curr_states))

    def enforcer_buffer(self, obj : RunningInstance):
        return format_html("<pre>{}</pre>", ", ".join(map(str, obj.enforcer.engine.get_buffer_items())))

admin.site.register(RunningInstance, RunningInstanceAdmin)
