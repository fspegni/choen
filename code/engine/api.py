from rest_framework import routers, serializers, viewsets

from engine.models import RunningInstance


class RunningInstanceSerializer(serializers.HyperlinkedModelSerializer):

    class Meta:
        model = RunningInstance
        fields = [ "id", "choreography", "engine_type", "label", "running",  ]

class RunningInstanceViewSet(viewsets.ModelViewSet):

    queryset = RunningInstance.objects.all()
    serializer_class = RunningInstanceSerializer
