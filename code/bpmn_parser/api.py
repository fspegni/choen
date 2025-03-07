from rest_framework import routers, serializers, viewsets

from bpmn_parser.models import Choreography


class ChoreographySerializer(serializers.HyperlinkedModelSerializer):

    class Meta:
        model = Choreography
        fields = [ "id", "name", "resource" ]

class ChoreographyViewSet(viewsets.ModelViewSet):

    queryset = Choreography.objects.all()
    serializer_class = ChoreographySerializer
