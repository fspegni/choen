from rest_framework import routers, serializers, viewsets

from engine.models import RunningInstance


class RunningInstanceSerializer(serializers.HyperlinkedModelSerializer):

    nfa = serializers.SerializerMethodField('field_nfa')
    rei = serializers.SerializerMethodField('field_rei')

    enforcer_states = serializers.SerializerMethodField("field_enforcer_states")
    enforcer_buffer = serializers.SerializerMethodField("field_enforcer_buffer")

    def field_nfa(self, obj):
        return str(obj.nfa)

    def field_rei(self, obj):
        try:
            return str(obj.rei)
        except Exception as e:
            return None

    def field_enforcer_states(self, obj):
        return obj.enforcer_states

    def field_enforcer_buffer(self, obj):
        return obj.enforcer_buffer


    class Meta:
        model = RunningInstance
        fields = [ "id", "choreography", "engine_type", "label", "nfa", "rei", "running", "execution_started", "execution_ended", "enforcer_states", "enforcer_buffer" ]


class RunningInstanceViewSet(viewsets.ModelViewSet):

    queryset = RunningInstance.objects.all()
    serializer_class = RunningInstanceSerializer
