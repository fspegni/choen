from django.test import TestCase
import solcx
import os
from django.conf import settings

from bpmn_parser.models import Choreography


class LoadChoreographyCase(TestCase):

    def setUp(self):

        c = Choreography()
        c.resource = os.path.join(settings.MEDIA_ROOT, "diagram.bpmn")
        c.save()

    def test_compilation(self):
        c = Choreography.objects.first()
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
        c = Choreography.objects.first()
        for curr in c.startEvents:
            print("START: %s" % curr)
            next = c.next(curr)
            print("NEXT: %s" % next)


    def test_prev(self):
        c = Choreography.objects.first()
        for curr in c.endEvents:
            print("END: %s" % curr)
            prev = c.prev(curr)
            print("PREV: %s" % prev)


    def test_next_star(self):
        c = Choreography.objects.first()
        for curr in c.startEvents:
            print("START: %s" % curr)
            items = c.star(curr, c.next)
            print("ITEMS = %s" % items)    


    def test_prev_star(self):
        c = Choreography.objects.first()
        for curr in c.endEvents:
            print("END: %s" % curr)
            items = c.star(curr, c.prev)
            print("ITEMS = %s" % items)    
