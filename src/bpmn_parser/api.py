from rest_framework import routers, serializers, viewsets

from bpmn_parser.models import Choreography


class ChoreographySerializer(serializers.HyperlinkedModelSerializer):

    rei = serializers.SerializerMethodField("get_rei_text")

    class Meta:
        model = Choreography
        fields = [ "id", "name", "resource", "rei" ]
        read_only = [ "rei", ]

    def get_rei_text(self, obj):
        return str(obj.to_rei())

class ChoreographyViewSet(viewsets.ModelViewSet):

    queryset = Choreography.objects.all()
    serializer_class = ChoreographySerializer
