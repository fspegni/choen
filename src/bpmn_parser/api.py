from rest_framework import routers, serializers, viewsets

from bpmn_parser.models import Choreography
import traceback

class ChoreographySerializer(serializers.HyperlinkedModelSerializer):

    rei = serializers.SerializerMethodField("get_rei_text")

    class Meta:
        model = Choreography
        fields = [ "id", "name", "resource", "rei" ]
        read_only = [ "rei", ]

    def get_rei_text(self, obj):
        rei_text = "N/N"
        try:
            rei_text = str(obj.to_rei())
        except Exception as err:
            rei_text = f"Error: {err}"
            traceback.print_exc()

        return rei_text

class ChoreographyViewSet(viewsets.ModelViewSet):

    queryset = Choreography.objects.all()
    serializer_class = ChoreographySerializer
