from django.contrib import admin, messages
#from django.utils.translation import ugettext as _
from django.utils.translation import gettext as _
from django.utils.html import format_html
from django_object_actions import DjangoObjectActions, action
# Register your models here.
from django import forms
from django.core.exceptions import ValidationError
from engine.models import RunningInstance, Configuration, Transaction, Contract, EngineOnChain, EngineOnChainMPST, EngineOffChain, EngineOffChainMPST, EngineHasContract
from django.contrib.admin import SimpleListFilter
from django.urls import reverse

import traceback

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

    list_display = [ "id", "label", "choreography", "mpst", "blockchain_configuration", "running", "is_onchain", "created_at", ]
    list_filter = [ "blockchain_configuration", "running", IsOnChainFilter, "created_at", ]
    search_fields = [ "id", "label", "choreography__name", "choreography__resource" ]

    fields = [ "label", "blockchain_configuration", "choreography", "running", "execution_started", "execution_ended", "rei", "automaton", "input_events", "output_events", "enforcer_states", "enforcer_buffer", "engine" ]

    readonly_fields = [ "blockchain_configuration", "execution_started", "execution_ended", "rei", "automaton", "enforcer_states",  "input_events", "output_events", "enforcer_buffer", "engine" ]

    change_actions = [ "action_start", "action_stop", ]
    changelist_actions = [ "action_start_all", "action_stop_all", ]

    def engine(self, obj : RunningInstance):

        #breakpoint()
        if obj is not None:
            if obj.engineonchain:
                url = reverse("admin:engine_engineonchain_change", args=[obj.engineonchain.pk])
                return format_html('<a href="{}">{}</a>', url, obj.engineonchain)
            elif obj.engineoffchain:
                url = reverse("admin:engine_engineoffchain_change", args=[obj.engineoffchain.pk])
                return format_html('<a href="{}">{}</a>', url, obj.engineonchain)

        return "-"
    engine.short_description = "Engine"


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
    readonly_fields = [ "running_instance", "choreography", "contract_address", "bytecode_size", "bytecode_hash", "deployed_at" ]

    def bytecode_size(self, obj: Contract):
        return obj.bytecode_size
    bytecode_size.short_description = _("bytecode size")


class IsPendingFilter(SimpleListFilter):

    title = "Is pending"
    parameter_name = "is_pending"
        
    def lookups(self, request, model_admin):
        return (
            ("yes", _("Yes")),
            ("no", _("No"))
        )

    def queryset(self, request, queryset):

        if self.value() == "yes":
            return queryset.exclude(transaction_hash=None).filter(receipt_hash=None)
        elif self.value() == "no":
            return queryset.exclude(receipt_hash=None)
        else:
            return queryset



@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):

    list_filter = [ "blockchain_configuration", IsPendingFilter ]
    list_display = [ "nonce", "blockchain_configuration", "transaction_hash", "receipt_hash", "is_pending", ] #"running_instance", ]
    search_fields = [ "transaction_hash", "receipt_hash" ] #"running_instance__configuration__address", ]

    actions = [ "check_receipts", ]

    @admin.display(boolean=True, description="Is pending")
    def is_pending(self, obj):
        return obj.is_pending

    @admin.action(description="Check transaction receipts")
    def check_receipts(self, request, queryset):
        for tx in queryset:
            try:
                tx.check_receipt()
                messages.success(request, f"Transaction is valid: {tx}")
            except Exception as err:
                traceback.print_exc()
                messages.error(request, f"Error checking validity: {tx} : {err}")



@admin.register(EngineOffChain)
class EngineOffChain(admin.ModelAdmin):
    list_display = [ "running_instance", "running_instance__choreography", "curr_states", "kb", "created_at" ]

    list_filter = [ "created_at", ]
    readonly_fields = ["rei", "created_at" ]

    def rei(self, obj : EngineOffChain):
        return format_html("<pre>{}</pre>", str(obj.running_instance.rei)) if obj.running_instance else None


@admin.register(EngineOnChain)
class EngineOnChain(admin.ModelAdmin):
    
    list_display = [ "running_instance", "running_instance__choreography", "created_at", "cost_gas", "cost_wei", "cost_eth", "overhead_build", "overhead_execution", "overhead_total" ]

    list_filter = [ "created_at", "blockchain_configuration" ]
    readonly_fields = ["rei", "contract_nfa_size", "contract_enforcer_size", "contracts_size", "created_at", "curr_states", "buffer", "kb", "cost_gas", "cost_wei", "cost_eth", "overhead_build", "overhead_execution", "overhead_total", ]

    def rei(self, obj : EngineOnChain):
        return format_html("<pre>{}</pre>", str(obj.running_instance.rei)) if obj.running_instance else None

    def curr_states(self, obj : EngineOnChain):

        return obj.get_curr_states()

    def buffer(self, obj : EngineOnChain):
    
        return obj.get_buffer_items()

    def kb(self, obj : EngineOnChain):

        return obj.get_kb()


@admin.register(EngineOffChainMPST)
class EngineOffChainMPST(admin.ModelAdmin):
    list_display = [ "running_instance", "running_instance__choreography", "curr_states", "created_at" ]

    list_filter = [ "created_at", ]
    readonly_fields = [ "created_at" ]


class EngineHasContractInline(admin.TabularInline):
    model = EngineHasContract
    extra = 1

@admin.register(EngineOnChainMPST)
class EngineOnChainMPST(admin.ModelAdmin):
    
    list_display = [ "running_instance", "running_instance__mpst", "blockchain_configuration", "created_at", ] # "cost_gas", "cost_wei", "cost_eth", ] # "overhead_build", "overhead_execution", "overhead_total" ]

    list_filter = [ "created_at", "blockchain_configuration", "running_instance__mpst" ]
    #readonly_fields = [ "contract_enforcer_size", "contracts_size", "created_at", "curr_states", "buffer", "cost_gas", "cost_wei", "cost_eth", ] # "overhead_build", "overhead_execution", "overhead_total", ]

    inlines = [ EngineHasContractInline ]

    def curr_states(self, obj : EngineOnChainMPST):

        return obj.get_curr_states()

    def buffer(self, obj : EngineOnChainMPST):
    
        return obj.get_buffer_items()
