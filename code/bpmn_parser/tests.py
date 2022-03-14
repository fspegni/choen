from django.test import TestCase
import solcx
import os
from django.conf import settings

from bpmn_parser.models import Choreography


class LoadChoreographyCase(TestCase):

    def setUp(self):

        c1 = Choreography()
        c1.name="diagram"
        c1.resource = os.path.join(settings.MEDIA_ROOT, "diagram.bpmn")
        c1.save()

        c2 = Choreography()
        c2.name = "diagram_gateways"
        c2.resource = os.path.join(settings.MEDIA_ROOT, "diagram_gateways.bpmn")
        c2.save()


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

        print("START: %s" % curr)
        next = c.next(curr)
        print("NEXT: %s" % next)

        assert(len(next) == 1)
        assert(next[0].attrib["name"] == "order pizza")


    def test_prev(self):

        c = Choreography.objects.get(name="diagram")

        assert len(c.endEvents) == 1

        curr = c.endEvents[0]

        assert len(c.incoming(curr)) == 1

        # for curr in c.endEvents:
        print(">>> END: %s" % curr)
        prev = c.prev(curr)
        print(">>> PREV: %s" % prev)

        assert len(prev) == 1
        assert prev[0].attrib["name"] == "deliver pizza"

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
  
