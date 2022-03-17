from django.test import TestCase
import solcx
import os
from django.conf import settings

from bpmn_parser.models import Choreography
import rei

class LoadChoreographyCase(TestCase):

    def setUp(self):

        choreographies = [
            ("diagram", "diagram.bpmn", ),
            ("diagram_basic", "diagram_basic.bpmn"),
            ("diagram_gateways", "diagram_gateways.bpmn", ),
            ("diagram_gateways_mismatch", "diagram_gateways_mismatch.bpmn", ),
            ("diagram_gateways_dangling", "diagram_gateways_dangling.bpmn", ),
            ("diagram_gateways_nested", "diagram_gateways_nested.bpmn", ),
            ("diagram_gateways_nested_intermediate", "diagram_gateways_nested_with_intermediate_task.bpmn", ),
            ("diagram_gateways_nested_inclusive", "diagram_gateways_nested_inclusive.bpmn", ),
            ("diagram_gateways_nested_dangling", "diagram_gateways_nested_dangling.bpmn", ),

        ]

        for name, filename in choreographies:
            c = Choreography()
            c.name = name
            c.resource = os.path.join(settings.MEDIA_ROOT, filename)
            c.save()



    def test_compilation(self):

        c = Choreography.objects.get(name="diagram")
        text = c.compile()
        assert len(text) > 0
        solc_version = "0.7.6"
        assert solc_version in text
        res = solcx.compile_source(text, solc_version=solc_version)

        key = "<stdin>:" + c.choreographies[0].attrib["id"]
        assert type(res) == dict
        assert key in res
        assert type(res[key]) == dict


    def test_next(self):

        c = Choreography.objects.get(name="diagram")

        assert len(c.startEvents) == 1

        curr = c.startEvents[0]
        # for curr in c.startEvents:

        assert len(c.outgoing(curr)) == 1

        # print("START: %s" % curr)
        next = c.next(curr)
        # print("NEXT: %s" % next)

        assert(len(next) == 1)
        assert(next[0].attrib["name"] == "order pizza")

        for curr in c.endEvents:
            next = c.next(curr)
            assert len(next) == 0


    def test_prev(self):

        c = Choreography.objects.get(name="diagram")

        assert len(c.endEvents) == 1

        curr = c.endEvents[0]

        assert len(c.incoming(curr)) == 1

        # for curr in c.endEvents:
        # print(">>> END: %s" % curr)
        prev = c.prev(curr)
        # print(">>> PREV: %s" % prev)

        assert len(prev) == 1
        assert prev[0].attrib["name"] == "deliver pizza"

        for curr in c.startEvents:
            prev = c.prev(curr)
            assert len(prev) == 0

    def test_next_star(self):

        c = Choreography.objects.get(name="diagram")
        # for curr in c.startEvents:
        curr = c.startEvents[0]

        # print("START: %s" % curr)
        items = c.star(curr, c.next)
        # print("ITEMS = %s" % items)

        # expected to return itself plus 4 reachable items
        assert len(items) == 5, f"Found {len(items)} items"


    def test_prev_star(self):

        c = Choreography.objects.get(name="diagram")
        for curr in c.endEvents:
            # print("END: %s" % curr)
            items = c.star(curr, c.prev)
            # print("ITEMS = %s" % items) 


    def test_reachable(self):

        c = Choreography.objects.get(name="diagram")
        # for curr in c.startEvents:
        curr = c.startEvents[0]

        # print("START: %s" % curr)
        items = c.reachable(curr)
        # print("ITEMS = %s" % items)

        # expected to return itself plus 4 reachable items
        assert len(items) == 5, f"Found {len(items)} items"


    def test_gateways(self):

        c = Choreography.objects.get(name="diagram_gateways")
        # for curr in c.startEvents:
        # curr = c.startEvents[0]

        assert len(c.gw_parallel) == 0
        assert len(c.gw_exclusive) == 2


    def test_neighbor(self):
        
        c = Choreography.objects.get(name="diagram_gateways")
        
        curr = c.startEvents[0]

        to_visit = set([ curr ])

        while len(to_visit) > 0:

            curr = to_visit.pop()
            # print(f">> TO VISIT: {curr} ({curr.attrib['id']})")

            arcs = c.outgoing(curr)
            # assert len(arcs) == 1, f"Found {len(arcs)} outgoing arcs from {curr} ({curr.attrib['id']})"

            if len(arcs) > 0:
                neighbors = c.next(curr, arcs[0])
                assert len(neighbors) == len(arcs)

                to_visit = to_visit.union(set(neighbors))
            else:
                neighbors = c.next(curr)
                assert len(neighbors) == 0


    def test_translation_basic(self):

        c = Choreography.objects.get(name="diagram_basic")
        r, match = rei.ChoToRei(c)

        print(f"REI ({c.name}): {r}")
        print(f"REI ({c.name},latex): {r.latex}")

        assert str(r) == "start end"

  
    def test_translation_simple(self):

        c = Choreography.objects.get(name="diagram")
        
        r, match = rei.ChoToRei(c)

        print(f"REI ({c.name}): {r}")
        print(f"REI ({c.name},latex): {r.latex}")

        assert str(r) == "start 'order pizza' 'hand over pizza' 'deliver pizza' end", f"Received: {r}"

    
    def test_translation_gateways(self):

        c = Choreography.objects.get(name="diagram_gateways")
        
        r, match = rei.ChoToRei(c)

        print(f"REI ({c.name}): {r}")
        print(f"REI ({c.name},latex): {r.latex}")

        assert str(r) == "start 'order pizza' ('New Activity' | 'hand over pizza' 'deliver pizza') end", f"Received: {r}"

    def test_translation_gateways_mismatch(self):

        c = Choreography.objects.get(name="diagram_gateways_mismatch")
        
        try:
            r, match = rei.ChoToRei(c)
            assert False, f"Expected excepion during the convertion. Received: {r}"
        except AssertionError:
            # this error is expected, because of a mismatch in the use of gateways
            assert True

    def test_translation_gateways_dangling(self):

        c = Choreography.objects.get(name="diagram_gateways_dangling")

        r, match = rei.ChoToRei(c)

        print(f"REI ({c.name}): {r}")
        print(f"REI ({c.name},latex): {r.latex}")

        assert str(r) == "start 'order pizza' ('New Activity' end | 'hand over pizza' 'deliver pizza' end)", f"Received: {r}"

        
    def test_translation_gateways_nested(self):

        c = Choreography.objects.get(name="diagram_gateways_nested")
        
        r, match = rei.ChoToRei(c)

        print(f"REI ({c.name}): {r}")
        print(f"REI ({c.name},latex): {r.latex}")

        assert str(r) == "start 'order pizza' ('New Activity' | 'hand over pizza' 'deliver pizza' (Something 'Something else' & 'Another task')) end", f"Received: {r}"


    def test_translation_gateways_nested_inclusive(self):

        c = Choreography.objects.get(name="diagram_gateways_nested_inclusive")
        
        r, match = rei.ChoToRei(c)

        print(f"REI ({c.name}): {r}")
        print(f"REI ({c.name},latex): {r.latex}")

        assert str(r) == "start 'order pizza' (('' | 'New Activity') & ('' | 'hand over pizza' 'deliver pizza' (Something 'Something else' & 'Another task'))) end", f"Received: {r}"

    
    def test_translation_gateways_nested_intermediate(self):

        c = Choreography.objects.get(name="diagram_gateways_nested_intermediate")
        
        r, match = rei.ChoToRei(c)

        print(f"REI ({c.name}): {r}")
        print(f"REI ({c.name},latex): {r.latex}")

        assert str(r) == "start 'order pizza' ('New Activity' | 'hand over pizza' 'deliver pizza' (Something 'Something else' & 'Another task') Intermediate) end", f"Received: {r}"

