from re import A
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
        # self._parsed = None
        self._tree = None

    @property
    def tree(self):

        # if not self._parsed:

        if not self._tree:
            self._tree = ET.parse(self.resource.path) #'country_data.xml')
            #self._parsed = tree.getroot()
            
        return self._tree #self._parsed

    @property
    def root(self):
        return self.tree.getroot()

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # self._parsed = None
        self._tree = None
 
    @property   
    def choreographies(self):
        return self.root.findall(".//bpmn2:choreography", NS)    

    @property   
    def messages(self):
        return self.root.findall(".//bpmn2:message", NS)    

    @property
    def participants(self):
        return self.root.findall(".//bpmn2:participant", NS)

    @property
    def tasks(self):
        return self.root.findall(".//bpmn2:choreographyTask", NS)

    @property
    def startEvents(self):
        return self.root.findall(".//bpmn2:startEvent", NS)

    @property
    def endEvents(self):
        return self.root.findall(".//bpmn2:endEvent", NS)

    def fetch(self, tag, **attributes):
        query = f".//bpmn2:{tag}"

        if attributes:
            query += "[" + ",".join(map(lambda p: f"@{p[0]}='{p[1]}'", attributes.items())) + "]"

        return self.root.findall(query, NS)

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

    def next(self, node):

        res = []

        if (node):
            out = node.findall(".//bpmn2:outgoing", NS)

            for curr in out:
                print("OUT : %s -> %s " % (node, curr))
                print("%s (%s)" % (curr, curr.text))

                flow = self.root.find(".//bpmn2:sequenceFlow[@id='%s']" % curr.text, NS)
                print("Flows found: %s" % flow)

                if flow == None:
                    raise Exception("Cannot find flow: %s" % curr.text)

                # res.append(flow.attrib["targetRef"])
                target_id = flow.attrib["targetRef"]
                target_node = self.root.find(".//*[@id='%s']" % target_id, NS)
                if target_node == None:
                    raise Exception("Target node (%s) cannot be found" % target_id)

                res.append(target_node)

        return res


    def prev(self, node):

        res = []

        if (node):
            incoming = node.findall(".//bpmn2:incoming", NS)

            for curr in incoming:
                print("OUT : %s -> %s " % (node, curr))
                print("%s (%s)" % (curr, curr.text))

                flow = self.root.find(".//bpmn2:sequenceFlow[@id='%s']" % curr.text, NS)
                print("Flows found: %s" % flow)

                if flow == None:
                    raise Exception("Cannot find flow: %s" % curr.text)

                source_id = flow.attrib["sourceRef"]
                source_node = self.root.find(".//*[@id='%s']" % source_id, NS)
                if source_node == None:
                    raise Exception("Source node (%s) cannot be found" % source_id)

                res.append(source_node)

        return res
        

    def star(self, start, op):
        items = set([ start ])
        visited = set([])    
        
        
        while visited != items:
            for curr in items:
                if curr not in visited:
                    found = op(curr)
                    
                    print("VISIT: %s |-> %s" % (curr, found))

                    visited = visited.union([ curr ])
                    items = items.union(found)

        print("STAR(%s,%s) = %s" % (start, op,items))
        return items
