from rest_framework import status, routers, serializers, viewsets
from rest_framework.decorators import parser_classes, action
from rest_framework.response import Response
from rest_framework.parsers import JSONParser

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


    def __init__(self, *args, **kwargs):

        optional_fields = kwargs.pop("optional_fields", [])

        super().__init__(*args, **kwargs)


        for curr in optional_fields:
            self.fields[curr].required = False
            

class RunningInstanceViewSet(viewsets.ModelViewSet):

    queryset = RunningInstance.objects.all()
    serializer_class = RunningInstanceSerializer


    @action(detail=True, methods=["get","post"]) # TODO here get is only for debug
    @parser_classes((JSONParser,))
    def process_events(self, request, pk=None): 

        try:
            ri = self.get_object()
            serializer = RunningInstanceSerializer(data=request.data, context={"request": request}, optional_fields=["choreography"])
            if serializer.is_valid():
                events = map(lambda a: a.strip(), request.data.get("events", "").split(" "))
                if isinstance(events, str):
                    events = [ events ]
    
                result = { "input": [], "output": [] }

                for curr in events:

                    ri.append_input(curr)
                    out = ri.enforcer.process_input(curr)
                    result["input"].append(curr)
                    if out:
                        result["output"].extend(out.split(" "))
                        ri.append_output(out)

                    while True:
                        out1 = ri.enforcer.process_check()
                        if out1:
                            result["output"].extend(out1.split(" "))
                            ri.append_output(out1)
                        else:
                            break            
        
                if ri.enforcer.ended():
                    ri.stop()
                else:
                    ri.save()

                result["status"] = "done"
                result["ri_running"] = ri.running
                result["ri_execution_started"] = ri.execution_started
                result["ri_execution_ended"] = ri.execution_ended
                result["input_events"] = ri.input_events
                result["output_events"] = ri.output_events
                result["enforcer_states"] = ri.enforcer_states
                result["enforcer_buffer"] = ri.enforcer_buffer
                
    
                return Response(result)
            else:
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({ "error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["post","get"]) # TODO here get is only for debug
    def start(self, request, pk=None):
        try:
            ri = self.get_object()
            ri.start()
            return Response({"status":"done"})
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["post","get"]) # TODO here get is only for debug
    def stop(self, request, pk=None):
        try:
            ri = self.get_object()
            ri.stop()
            return Response({"status":"done"})
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
