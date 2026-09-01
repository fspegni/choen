from rest_framework import routers, serializers, viewsets

from mpst.models import MPST
import traceback

class MPSTSerializer(serializers.HyperlinkedModelSerializer):

    class Meta:
        model = MPST
        fields = [ "id", "name", "resource", "enabled", "details" ]

class MPSTViewSet(viewsets.ModelViewSet):

    queryset = MPST.objects.all()
    serializer_class = MPSTSerializer
