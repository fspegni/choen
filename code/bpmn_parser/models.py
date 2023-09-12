from re import A
from django.db import models
from django.conf import settings

from django.utils.translation import ugettext as _
from jinja2 import Environment, PackageLoader

import xml.etree.ElementTree as ET
from django.utils.text import slugify
# from nfa import ReiToNFA, NFA
# from rei import REI, ChoToRei

NS = {
    "bpmn2": "http://www.omg.org/spec/BPMN/20100524/MODEL",
}

ElementType=ET.Element

class Choreography(models.Model):

    name = models.TextField(max_length=100, null=True, blank=True)
    resource = models.FileField(upload_to=settings.UPLOAD_ROOT)

    class Meta:
    
        verbose_name = _("choreography")
        verbose_name_plural = _("choreographies")

    def __init__(self, *args, **kwargs):        
        super().__init__(*args, **kwargs)
        # self._parsed = None
        self._tree = None


    def __str__(self):
        return self.name

    @property
    def tree(self):

        # if not self._parsed:

        if self._tree is None:
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
    def all_messages(self):
        return self.root.findall(".//bpmn2:message", NS)    

    @property
    def all_participants(self):
        return self.root.findall(".//bpmn2:participant", NS)

    @property
    def tasks(self):
        return self.root.findall(".//bpmn2:choreographyTask", NS)

    @property
    def arrows(self):
        return self.root.findall(".//bpmn2:sequentialFlow", NS)

    @property
    def gw_exclusive(self):
        return self.root.findall(".//bpmn2:exclusiveGateway", NS)

    @property
    def gw_parallel(self):
        return self.root.findall(".//bpmn2:parallelGateway", NS)

    @property
    def gw_inclusive(self):
        return self.root.findall(".//bpmn2:inclusiveGateway", NS)

    @property
    def gateways(self):
        return self.gw_parallel + self.gw_exclusive + self.gw_inclusive

    @property
    def startEvents(self):
        return self.root.findall(".//bpmn2:startEvent", NS)

    @property
    def endEvents(self):
        return self.root.findall(".//bpmn2:endEvent", NS)

    def messages(self, node:ET.Element):
        messages = node.findall(".//bpmn2:messageFlowRef", NS)
        res = []
        for curr in messages:
            # print(f"Find flow def: {curr} : {curr.text}")
            msg_flow_def_xpath = f".//bpmn2:messageFlow[@id='{curr.text}']"
            msg_flow_def = self.root.find(msg_flow_def_xpath, NS)
            # print(f"Find msg def: {msg_flow_def} : {msg_flow_def.attrib['messageRef']}")
            msg_def_xpath = f"bpmn2:message[@id='{msg_flow_def.attrib['messageRef']}']"
            # print(f"Msg def xpath: {msg_def_xpath}")
            msg_def = self.root.find(msg_def_xpath, NS)
            msg_id = msg_def.attrib["id"]
            msg_name = msg_def.attrib.get("name")

            res.append(msg_name if msg_name else msg_id)

        return res


    def involved(self, node:ET.Element):
        p_initiating = node.attrib.get("initiatingParticipantRef")
        # assert p_initiating is not None, f"Null initiating in node {node.tag}:{node.attrib['id']}"

        p_ref = node.findall(".//bpmn2:participantRef", NS)

        if len(p_ref) == 0:
            # raise Exception("No participant for this node")
            return []

        initiating = None
        others = []
        for curr in p_ref:
            p_def_xpath = f".//bpmn2:participant[@id='{curr.text}']"
            # print(f"Participant definition xpath: {p_def_xpath}")
            p_def = self.root.find(p_def_xpath, NS)
            # print(f"Found participant definition: {p_def}")

            if p_def is None:
                raise Exception(f"Cannot find definition for participant: {curr.text}")

            if curr.text == p_initiating:
                initiating = p_def
            else:
                others.append(p_def)
            # participants[curr.text] = p_def #.attrib["name"]

        # assert initiating is not None, f"Could not find initiating {p_initiating} in node {node.tag}:{node.attrib['id']}"

        # res = [ participants.pop(p_initiating) ]

        return [ initiating ] + others


    def initiator(self, node:ET.Element):
        involved = self.involved(node)

        if involved:
            return involved[0]
        else:
            return None

    def recipients(self, node:ET.Element):
        return self.involved(node)[1:]


    def fetch(self, tag:str, **attributes):
        query = f".//bpmn2:{tag}"

        if attributes:
            query += "[" + ",".join(map(lambda p: f"@{p[0]}='{p[1]}'", attributes.items())) + "]"

        return self.root.findall(query, NS)


    def lookup(self, tag:str, **attributes):
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
        ctx = { "settings": settings, "choreography": self.choreographies[0], "participants": self.all_participants, "tasks": self.tasks }
        return template.render(**ctx)


    def outgoing(self, node:ElementType) -> set:
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


    def incoming(self, node:ET.Element) -> set:
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

    

    def next(self, node:ET.Element, connections=None) -> set:

        res = []

        if (node):
            if connections is None:
                connections = self.outgoing(node) #node.findall(".//bpmn2:outgoing", NS)
            elif isinstance(connections, ET.Element):
                connections = [ connections ]

            assert all(isinstance(element, ET.Element) for element in connections)

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


    def prev(self, node:ET.Element, connections=None) -> set:

        res = []

        if (node):
            if connections is None:
                # incoming = node.findall(".//bpmn2:incoming", NS)
                connections = self.incoming(node)
            elif isinstance(connections, ET.Element):
                connections = [ connections ]
            
            assert all(isinstance(element, ET.Element) for element in connections)
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


    def star(self, start:ET.Element, op) -> set:
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

    def reachable(self, start:ET.Element) -> set:
        return self.star(start, self.next)


    def node_type(self, node:ET.Element) -> str:
        if node is None:
            # print(f">>> {node} -> None type")
            return None
        
        res = "NN"

        if node.tag == f"{{{NS['bpmn2']}}}choreographyTask":
            res = "TASK"
        elif node.tag == f"{{{NS['bpmn2']}}}startEvent":
            res = "START"
        elif node.tag == f"{{{NS['bpmn2']}}}endEvent":
            res = "END"
        elif node.tag == f"{{{NS['bpmn2']}}}exclusiveGateway":
            
            incoming = self.incoming(node)
            outgoing = self.outgoing(node)

            if len(incoming) == 1 and len(outgoing) > 1:
                res = "GW_EX_OPEN"
            elif len(incoming) > 1 and len(outgoing) == 1:
                res = "GW_EX_CLOSE"
            else:
                res = f"GW_EX({len(incoming)},{len(outgoing)})"


        elif node.tag == f"{{{NS['bpmn2']}}}parallelGateway":
            incoming = self.incoming(node)
            outgoing = self.outgoing(node)

            if len(incoming) == 1 and len(outgoing) > 1:
                res = "GW_PAR_OPEN"
            elif len(incoming) > 1 and len(outgoing) == 1:
                res = "GW_PAR_CLOSE"
            else:
                res = f"GW_PAR({len(incoming)},{len(outgoing)})"

        elif node.tag == f"{{{NS['bpmn2']}}}inclusiveGateway":
            incoming = self.incoming(node)
            outgoing = self.outgoing(node)

            if len(incoming) == 1 and len(outgoing) > 1:
                res = "GW_INC_OPEN"
            elif len(incoming) > 1 and len(outgoing) == 1:
                res = "GW_INC_CLOSE"
            else:
                res = f"GW_INC({len(incoming)},{len(outgoing)})"


        return res

    def to_rei(self):
        from rei import ChoToRei, render_receive
        exp, closure = ChoToRei(self, render_receive)
        print("REI:", exp)
        return exp

    def to_nfa(self):
        from nfa import ReiToNFA
        rei = self.to_rei()
        automaton = ReiToNFA(rei)
        return automaton
