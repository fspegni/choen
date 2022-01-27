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
