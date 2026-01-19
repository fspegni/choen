from django.contrib import admin
#from django.utils.translation import ugettext as _
from django.utils.translation import gettext as _
from django.utils.html import format_html
from django_object_actions import DjangoObjectActions, action
# Register your models here.
from django import forms
from django.core.exceptions import ValidationError
from engine.models import RunningInstance, Configuration, Transaction, Contract, EngineOnChain, EngineOffChain
from django.contrib.admin import SimpleListFilter

class ConfigurationForm(forms.ModelForm):

    class Meta:
        model = Configuration
        exclude = []
        widgets = {
            'private_key': forms.PasswordInput(),
        }


@admin.register(Configuration)
class ConfigurationAdmin(admin.ModelAdmin):

    form = ConfigurationForm

    list_display = [ "label", "chain_id", "url", ]
    search_fields = [ "chain_id", "url", "address", "private_key", ]

    

class IsOnChainFilter(SimpleListFilter):

    title = "Is onchain"
    parameter_name = "is_onchain"
        
    def lookups(self, request, model_admin):
        return (
            ("yes", _("Yes")),
            ("no", _("No"))
        )

    def queryset(self, request, queryset):

        if self.value() == "yes":
            return queryset.exclude(blockchain_configuration=None)
        elif self.value() == "no":
            return queryset.filter(blockchain_configuration=None)
        else:
            return queryset

@admin.register(RunningInstance)
class RunningInstanceAdmin(DjangoObjectActions, admin.ModelAdmin):

    list_display = [ "id", "label", "choreography", "running", "is_onchain", "created_at", ]
    list_filter = [ "blockchain_configuration", "running", IsOnChainFilter, "created_at", ]
    search_fields = [ "id", "label", "choreography__name", "choreography__resource" ]

    fields = [ "label", "blockchain_configuration", "choreography", "running", "execution_started", "execution_ended", "rei", "automaton", "input_events", "output_events", "enforcer_states", "enforcer_buffer", ]

    readonly_fields = [ "blockchain_configuration", "execution_started", "execution_ended", "rei", "automaton", "enforcer_states",  "input_events", "output_events", "enforcer_buffer", ]

    change_actions = [ "action_start", "action_stop", ]
    changelist_actions = [ "action_start_all", "action_stop_all", ]

    @admin.display(boolean=True, description="Is onchain")
    def is_onchain(self, obj):
        return obj.blockchain_configuration is not None

    @action(label=_("Start"), description=_("Start the current instance"))
    def action_start(self, request, obj):
        obj.start()


    @action(label=_("Start"), description=_("Start the selected instance(s)"))
    def action_start_all(self, request, queryset):
        for curr in queryset.all():
            self.action_start(request, curr)


    @action(label=_("Stop"), description=_("Stop the current instance"))
    def action_stop(self, request, obj):
        obj.stop()


    @action(label=_("Stop"), description=_("Stop the selected instance(s)"))
    def action_stop_all(self, request, queryset):
        for curr in queryset.all():
            self.action_stop(request, curr)


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
        #print(obj.enforcer)
        if not obj or not obj.enforcer or not obj.enforcer_states:
            return ""

        return format_html("<pre>{}</pre>", ", ".join(obj.enforcer_states))

    def enforcer_buffer(self, obj : RunningInstance):
        if not obj or not obj.enforcer or not obj.enforcer_buffer:
            return ""

        return format_html("<pre>{}</pre>", ", ".join(map(str, obj.enforcer_buffer)))

@admin.register(Contract)
class ContractAdmin(admin.ModelAdmin):

    list_display = [ "label", "contract_address", "running_instance", "choreography", "deployed_at" ]
    search_fields = [ "label", "contract_address", "running_instance__configuration__address", ]

    list_filter = [ "label", "deployed_at" ] 
    readonly_fields = [ "running_instance", "choreography", "contract_address", "bytecode_size", "deployed_at" ]

    def bytecode_size(self, obj: Contract):
        return obj.bytecode_size
    bytecode_size.short_description = _("bytecode size")

@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):

    list_display = [ "tx_hash", "block_number", ] #"running_instance", ]
    search_fields = [ "tx_hash", "block_hash", "block_number",  ] #"running_instance__configuration__address", ]

@admin.register(EngineOffChain)
class EngineOffChain(admin.ModelAdmin):
    list_display = [ "running_instance", "running_instance__choreography", "curr_states", "kb", "created_at" ]

    list_filter = [ "created_at", ]
    readonly_fields = ["rei", "created_at" ]

    def rei(self, obj : EngineOffChain):
        return format_html("<pre>{}</pre>", str(obj.running_instance.rei)) if obj.running_instance else None


@admin.register(EngineOnChain)
class EngineOnChain(admin.ModelAdmin):
    
    list_display = [ "running_instance", "running_instance__choreography", "created_at", ]

    list_filter = [ "created_at", "blockchain_configuration" ]
    readonly_fields = ["rei", "contract_nfa_size", "contract_enforcer_size", "contracts_size", "created_at" ]

    def rei(self, obj : EngineOnChain):
        return format_html("<pre>{}</pre>", str(obj.running_instance.rei)) if obj.running_instance else None


