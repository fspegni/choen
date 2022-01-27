from django.db import models
from django.conf import settings

from jinja2 import Environment, PackageLoader

import xml.etree.ElementTree as ET
from django.utils.text import slugify


NS = {
    "bpmn2": "http://www.omg.org/spec/BPMN/20100524/MODEL",
}

class Choreography(models.Model):

    resource = models.FileField(upload_to=settings.UPLOAD_ROOT)

    def __init__(self, *args, **kwargs):        
        super().__init__(*args, **kwargs)
        self._parsed = None

    @property
    def parsed(self):

        if not self._parsed:

            tree = ET.parse(self.resource.path) #'country_data.xml')
            self._parsed = tree.getroot()
            
        return self._parsed

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self._parsed = None
 
    @property   
    def choreographies(self):
        return self.parsed.findall(".//bpmn2:choreography", NS)    

    @property   
    def messages(self):
        return self.parsed.findall(".//bpmn2:message", NS)    

    @property
    def participants(self):
        return self.parsed.findall(".//bpmn2:participant", NS)

    @property
    def tasks(self):
        return self.parsed.findall(".//bpmn2:choreographyTask", NS)

    @property
    def startEvents(self):
        return self.parsed.findall(".//bpmn2:startEvent", NS)

    @property
    def endEvents(self):
        return self.parsed.findall(".//bpmn2:endEvent", NS)

    def fetch(self, tag, **attributes):
        query = f".//bpmn2:{tag}"

        if attributes:
            query += "[" + ",".join(map(lambda p: f"@{p[0]}='{p[1]}'", attributes.items())) + "]"

        return self.parsed.findall(query, NS)

    def lookup(self, tag, **attributes):
        results = self.fetch(tag, **attributes)
    
        if len(results) == 0:
            raise Exception("No results found with passed criteria")
        elif len(results) > 1:
            raise Exception("Too many results found with passed criteria")

        return results[0]

    def compile(self):
        
        env = Environment(loader=PackageLoader('bpmn_parser'))
        env.filters["slugify"] = lambda v: slugify(v).replace("-", "_")
        template = env.get_template(settings.TEMPLATE_NAME)
        ctx = { "settings": settings, "choreography": self.choreographies[0], "participants": self.participants, "tasks": self.tasks }
        return template.render(**ctx)
