from django.test import TestCase
import solcx
import os
from django.conf import settings

from bpmn_parser.models import Choreography, NS, ElementType
import rei

class TestChoreographyBasicCase(TestCase):

    def setUp(self):

        choreographies = [
            ("diagram", "diagram.bpmn", ),
            ("diagram_gateways", "diagram_gateways.bpmn", ),
        ]

        for name, filename in choreographies:
            c:Choreography = Choreography()
            c.name = name
            c.resource = os.path.join(settings.MEDIA_ROOT, filename)
            c.save()



    def test_compilation(self):

        c:Choreography = Choreography.objects.get(name="diagram")
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

        c:Choreography = Choreography.objects.get(name="diagram")

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

        c:Choreography = Choreography.objects.get(name="diagram")

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

        c:Choreography = Choreography.objects.get(name="diagram")
        # for curr in c.startEvents:
        curr = c.startEvents[0]

        # print("START: %s" % curr)
        items = c.star(curr, c.next)
        # print("ITEMS = %s" % items)

        # expected to return itself plus 4 reachable items
        assert len(items) == 5, f"Found {len(items)} items"


    def test_prev_star(self):

        c:Choreography = Choreography.objects.get(name="diagram")
        for curr in c.endEvents:
            # print("END: %s" % curr)
            items = c.star(curr, c.prev)
            # print("ITEMS = %s" % items) 


    def test_reachable(self):

        c:Choreography = Choreography.objects.get(name="diagram")
        # for curr in c.startEvents:
        curr = c.startEvents[0]

        # print("START: %s" % curr)
        items = c.reachable(curr)
        # print("ITEMS = %s" % items)

        # expected to return itself plus 4 reachable items
        assert len(items) == 5, f"Found {len(items)} items"


    def test_gateways(self):

        c:Choreography = Choreography.objects.get(name="diagram_gateways")
        # for curr in c.startEvents:
        # curr = c.startEvents[0]

        assert len(c.gw_parallel) == 0
        assert len(c.gw_exclusive) == 2


    def test_visit_neighbor(self):
        """
        This test case shows also how to build a visitor using the next(...) function
        """
        
        c:Choreography = Choreography.objects.get(name="diagram_gateways")
        
        curr = c.startEvents[0]

        to_visit = set([ curr ])
        visited = set([])
        n_visited = 0

        while len(to_visit) > 0:

            curr = to_visit.pop()
            visited.add(curr)

            n_visited = n_visited + 1
            # print(f">> TO VISIT: {curr} ({curr.attrib['id']})")

            arcs = c.outgoing(curr)
            # assert len(arcs) == 1, f"Found {len(arcs)} outgoing arcs from {curr} ({curr.attrib['id']})"
            # print(f">> ARCS: {arcs}")

            if len(arcs) > 0:
                neighbors = c.next(curr, arcs)
                assert len(neighbors) == len(arcs), f"Received: neighbors : {neighbors} : arcs : {arcs}"

                # remove from the neighbors, those that have been visited
                neighbors_unvisited = set(neighbors).difference(visited)
                to_visit = to_visit.union(set(neighbors_unvisited))
            else:
                neighbors = c.next(curr)
                assert len(neighbors) == 0

        n_start = len(c.startEvents)
        n_end = len(c.endEvents)
        n_tasks = len(c.tasks)
        n_gateways = len(c.gateways)

        assert n_visited == n_start + n_end + n_tasks + n_gateways, f"Visited: {n_visited} : Start: {n_start} : End: {n_end} : Tasks: {n_tasks} : Gateways: {n_gateways}"

    def test_start_end_have_no_participants(self):

        c:Choreography = Choreography.objects.get(name="diagram_gateways")

        for curr in c.startEvents:
            participants = c.involved(curr)

            assert len(participants) == 0

        for curr in c.endEvents:
            participants = c.involved(curr)

            assert len(participants) == 0


class TestTranslateChoreographyToRei(TestCase):

    def setUp(self):

        choreographies = [
            ("diagram", "diagram.bpmn", ),
            ("diagram_minimal", "diagram_minimal.bpmn"),
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
            c:Choreography = Choreography()
            c.name = name
            c.resource = os.path.join(settings.MEDIA_ROOT, filename)
            c.save()
            

    def test_translation_only_start(self):
        """
        This diagram contains only a start event
        """
        c:Choreography = Choreography.objects.get(name="diagram_minimal")

        print(f"{NS}")
        # print(f">>> START: {c.startEvents}")
        print(f"{type(c.startEvents[0])}")

        r, match = rei.ChoToRei(c)

        print(f"REI ({c.name}): {r}")
        print(f"REI ({c.name},latex): {r.latex}")

        assert str(r) == "^$"


    def test_translation_start_end(self):
        """
        This diagram contains only a start event followed by an end event
        """
        c:Choreography = Choreography.objects.get(name="diagram_basic")

        # print(f">>> START: {c.startEvents}")


        r, match = rei.ChoToRei(c)

        print(f"REI ({c.name}): {r}")
        print(f"REI ({c.name},latex): {r.latex}")

        assert str(r) == "^$", f"Received: {r}"

  
    def test_translation_simple(self):

        c:Choreography = Choreography.objects.get(name="diagram")
        
        r, match = rei.ChoToRei(c)

        print(f"REI ({c.name}): {r}")
        print(f"REI ({c.name},latex): {r.latex}")

        assert str(r) == "^'order pizza' 'hand over pizza' 'deliver pizza'$", f"Received: {r}"

    
    def test_translation_gateways(self):

        c:Choreography = Choreography.objects.get(name="diagram_gateways")
        
        r, match = rei.ChoToRei(c)

        print(f"REI ({c.name}): {r}")
        print(f"REI ({c.name},latex): {r.latex}")

        assert str(r) == "^'order pizza' ('New Activity' | 'hand over pizza' 'deliver pizza')$", f"Received: {r}"

    def test_translation_gateways_mismatch(self):

        c:Choreography = Choreography.objects.get(name="diagram_gateways_mismatch")
        
        try:
            r, match = rei.ChoToRei(c)
            assert False, f"Expected excepion during the convertion. Received: {r}"
        except AssertionError:
            # this error is expected, because of a mismatch in the use of gateways
            assert True

    def test_translation_gateways_dangling(self):

        c:Choreography = Choreography.objects.get(name="diagram_gateways_dangling")

        r, match = rei.ChoToRei(c)

        print(f"REI ({c.name}): {r}")
        print(f"REI ({c.name},latex): {r.latex}")

        assert str(r) == "^'order pizza' ('New Activity'$ | 'hand over pizza' 'deliver pizza'$)", f"Received: {r}"

        
    def test_translation_gateways_nested(self):

        c:Choreography = Choreography.objects.get(name="diagram_gateways_nested")
        
        r, match = rei.ChoToRei(c)

        print(f"REI ({c.name}): {r}")
        print(f"REI ({c.name},latex): {r.latex}")

        assert str(r) == "^'order pizza' ('New Activity' | 'hand over pizza' 'deliver pizza' (Something 'Something else' & 'Another task'))$", f"Received: {r}"


    def test_translation_gateways_nested_inclusive(self):

        c:Choreography = Choreography.objects.get(name="diagram_gateways_nested_inclusive")
        
        r, match = rei.ChoToRei(c)

        print(f"REI ({c.name}): {r}")
        print(f"REI ({c.name},latex): {r.latex}")

        assert str(r) == "^'order pizza' (('' | 'New Activity') & ('' | 'hand over pizza' 'deliver pizza' (Something 'Something else' & 'Another task')))$", f"Received: {r}"

    
    def test_translation_gateways_nested_intermediate(self):

        c:Choreography = Choreography.objects.get(name="diagram_gateways_nested_intermediate")
        
        r, match = rei.ChoToRei(c)

        print(f"REI ({c.name}): {r}")
        print(f"REI ({c.name},latex): {r.latex}")

        assert str(r) == "^'order pizza' ('New Activity' | 'hand over pizza' 'deliver pizza' (Something 'Something else' & 'Another task') Intermediate)$", f"Received: {r}"


    def test_translation_gateways_nested_dangling(self):

        c:Choreography = Choreography.objects.get(name="diagram_gateways_nested_dangling")

        r, match = rei.ChoToRei(c)


        print(f"REI ({c.name}): {r}")
        print(f"REI ({c.name},latex): {r.latex}")

        assert str(r) == "^'order pizza' ('New Activity' ('another implicit end'$ & (('' | 'implicit end'$) & ('' | something 'something else'$))) | 'hand over pizza' 'deliver pizza'$)", f"Received: {r}"

    def test_translation_with_messages(self):

        def handle_task (cho:Choreography, node:ElementType):
            print(f"Choreography: {cho}")
            print(f"Node: {node} : {node.attrib['id']} : {node.attrib.get('name')}")
            messages = cho.messages(node)

            symbol = node.attrib["id"]
            if len(messages) > 0:
                initiator = cho.initiator(node)
                recipients = cho.recipients(node)

                assert len(recipients) == 1
                target = recipients[0].replace(" ", "_")
                msg = messages[0].replace(" ","_")
                symbol = f"{target}?{msg}"

            return rei.Symbol(symbol)


        c:Choreography = Choreography.objects.get(name="diagram_gateways_nested_dangling")

        r, match = rei.ChoToRei(c, handle_task)

        print(f"REI ({c.name}): {r}")
        print(f"REI ({c.name},latex): {r.latex}")

        assert str(r) == "^'order pizza' ('New Activity' ('another implicit end'$ & (('' | 'implicit end'$) & ('' | something 'something else'$))) | 'hand over pizza' 'deliver pizza'$)", f"Received: {r}"
