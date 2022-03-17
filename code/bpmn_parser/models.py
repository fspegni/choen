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

    name = models.TextField(max_length=100, null=True, blank=True)
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
    def arrows(self):
        return self.root.findAll(".//bpmn2:sequentialFlow", NS)

    @property
    def gw_exclusive(self):
        return self.root.findall(".//bpmn2:exclusiveGateway", NS)

    @property
    def gw_parallel(self):
        return self.root.findall(".//bpmn2:parallelGateway", NS)

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

    def outgoing(self, node):
        res = []

        if (node):
            outgoing = node.findall(".//bpmn2:outgoing", NS)
            #res.append(out)

            for curr in outgoing:
                # print(f"OUT : {node} -> {curr} ")
                # print(f"{curr} ({curr.text})")

                flow = self.root.find(f".//bpmn2:sequenceFlow[@id='{curr.text}']", NS)
                # print(f"Flows found: {flow}")

                if flow == None:
                    raise Exception(f"Cannot find flow: {curr.text}")

                res.append(flow)

        return res


    def incoming(self, node):
        res = []

        if (node):
            incoming = node.findall(".//bpmn2:incoming", NS)
            #res.append(out)

            for curr in incoming:
                # print("IN : %s -> %s " % (node, curr))
                # print("%s (%s)" % (curr, curr.text))

                flow = self.root.find(".//bpmn2:sequenceFlow[@id='%s']" % curr.text, NS)
                # print("Flows found: %s" % flow)

                if flow == None:
                    raise Exception("Cannot find flow: %s" % curr.text)

                res.append(flow)

        return res

    

    def next(self, node, connection=None):

        res = []

        if (node):
            if not connection:
                connections = self.outgoing(node) #node.findall(".//bpmn2:outgoing", NS)
            else:
                connections = [ connection ]

            for flow in connections:
            # for curr in out:
                # print("OUT : %s -> %s " % (node, curr))
                # print("%s (%s)" % (curr, curr.text))

                # flow = self.root.find(".//bpmn2:sequenceFlow[@id='%s']" % curr.text, NS)
                # print("Flows found: %s" % flow)

                # if flow == None:
                    # raise Exception("Cannot find flow: %s" % curr.text)

                # res.append(flow.attrib["targetRef"])
                target_id = flow.attrib["targetRef"]
                target_node = self.root.find(".//*[@id='%s']" % target_id, NS)
                if target_node == None:
                    raise Exception("Target node (%s) cannot be found" % target_id)

                res.append(target_node)

        return res


    def prev(self, node, connection=None):

        res = []

        if (node):
            if not connection:
                # incoming = node.findall(".//bpmn2:incoming", NS)
                connections = self.incoming(node)
            else:
                connections = [ connection ]

            # for curr in incoming:
            #     print("OUT : %s -> %s " % (node, curr))
            #     print("%s (%s)" % (curr, curr.text))

            #     flow = self.root.find(".//bpmn2:sequenceFlow[@id='%s']" % curr.text, NS)
            #     print("Flows found: %s" % flow)

            #     if flow == None:
            #         raise Exception("Cannot find flow: %s" % curr.text)

            for flow in connections:

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
                    
                    # print("VISIT: %s |-> %s" % (curr, found))

                    visited = visited.union([ curr ])
                    items = items.union(found)

        # print("STAR(%s,%s) = %s" % (start, op,items))
        return items

    def reachable(self, start):
        return self.star(start, self.next)


    def node_type(self, node):
        if not node:
            return None
        
        res = "NN"
        if node.tag == f"{{{NS['bpmn2']}}}exclusiveGateway":
            
            incoming = self.incoming(node)
            outgoing = self.outgoing(node)

            if len(incoming) == 1 and len(outgoing) > 1:
                res = "GW_EX_OPEN"
            elif len(incoming) > 1 and len(outgoing) == 1:
                res = "GW_EX_CLOSE"
            else:
                # print(f"No. incoming: {len(incoming)} - No. outgoing: {len(outgoing)} - Node: {node}")
                res = f"GW_EX({len(incoming)},{len(outgoing)})"


        elif node.tag == f"{{{NS['bpmn2']}}}parallelGateway":
            incoming = self.incoming(node)
            outgoing = self.outgoing(node)

            if len(incoming) == 1 and len(outgoing) > 1:
                res = "GW_PAR_OPEN"
            elif len(incoming) > 1 and len(outgoing) == 1:
                res = "GW_PAR_CLOSE"
            else:
                # print(f"No. incoming: {len(incoming)} - No. outgoing: {len(outgoing)} - Node: {node}")
                res = f"GW_PAR({len(incoming)},{len(outgoing)})"

        elif node.tag == f"{{{NS['bpmn2']}}}inclusiveGateway":
            incoming = self.incoming(node)
            outgoing = self.outgoing(node)

            if len(incoming) == 1 and len(outgoing) > 1:
                res = "GW_INC_OPEN"
            elif len(incoming) > 1 and len(outgoing) == 1:
                res = "GW_INC_CLOSE"
            else:
                # print(f"No. incoming: {len(incoming)} - No. outgoing: {len(outgoing)} - Node: {node}")
                res = f"GW_INC({len(incoming)},{len(outgoing)})"

        elif node.tag == f"{{{NS['bpmn2']}}}choreographyTask":
            res = "TASK"
        elif node.tag == f"{{{NS['bpmn2']}}}startEvent":
            res = "START"
        elif node.tag == f"{{{NS['bpmn2']}}}endEvent":
            res = "END"

        # TODO add inclusive gateway

        return res
