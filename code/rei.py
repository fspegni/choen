from bpmn_parser.models import Choreography, ElementType
# import re

def expect_node_type(cho:Choreography, node:ElementType, ntypes):

    if isinstance(ntypes, str):
        ntypes = [ ntypes] 

    real_ntype = cho.node_type(node)
    assert real_ntype in ntypes, f"Expected node of type '{ntypes}'. Found: Node: {node} - Type: {real_ntype}"


class REI:

    def __str__(self):
        return ""


    def __bytes__(self):
        return str(self).encode('utf-8')

    @property
    def latex(self):
        return ""




class Symbol(REI):

    def __init__(self, symbol:str):
        self.symbol = symbol

    def __str__(self):
        res = self.symbol

        if " " in res or not res:
            res = f"'{res}'"
    
        return res

    @property
    def latex(self):
        return f"\\textit{{{self.symbol}}}"

class Epsilon(Symbol):

    def __init__(self):
        self.symbol = ""

    @property
    def latex(self):
        return f"\\epsilon"


class Start(Symbol):

    def __init__(self):
        self.symbol = "^"

    @property
    def latex(self):
        return "\\hat{}"

class End(Symbol):

    def __init__(self):
        self.symbol = "$"

    @property
    def latex(self):
        return f"\\$"        

class Star(REI):

    def __init__(self, rei:REI):
        self.rei = rei
    
    def __str__(self):
        if isinstance(self.rei, Symbol):
            return f"{self.rei}*"
        else:
            return f"({self.rei})*"

    @property
    def latex(self):
        if isinstance(self.rei, Symbol):
            return f"{{{self.rei.latex}}}^\star"
        else:
            return f"({self.rei})^\star"


class Conc(REI):

    def __init__(self, *children):
        if len(children) == 0:
            raise Exception("Empty lists are not accepted here")

        self.items = []

        for curr in children:
            if isinstance(curr, Conc):
                self.items.extend(curr.items)
            else:
                if isinstance(curr, str):
                    curr = Symbol(curr)

                self.items.append(curr)

        # self.items = list(items)

    def __str__(self):
        text = ""
        eat_space = False
        for curr in self.items:
            if eat_space or isinstance(curr, End):
                text = f"{text}{curr}"
            else:
                text = f"{text} {curr}"

            # remember to eat one space next round
            eat_space = isinstance(curr, Start) or isinstance(curr, End)
                
        
        return text.strip()

    @property
    def latex(self):
        return " \\cdot ".join(map(lambda curr: str(curr.latex) if curr else "", self.items))


class Par(REI):

    def __init__(self, *items):
        self.items = list(map(lambda curr: Symbol(curr) if isinstance(curr, str) else curr, items))

    def __str__(self):
        return "(" + " & ".join(map(lambda curr: str(curr), self.items)) + ")"

    @property
    def latex(self):
        return "(" + " \& ".join(map(lambda curr: curr.latex if curr else "", self.items)) + ")"


class Union(REI):

    def __init__(self, *items):
        self.items = list(map(lambda curr: Symbol(curr) if isinstance(curr, str) else curr, items))

    def __str__(self):
        return "(" + " | ".join(map(lambda curr: str(curr), self.items)) + ")"

    @property
    def latex(self):
        return "(" + " \\vert ".join(map(lambda curr: curr.latex if curr else "", self.items)) + ")"


class NFA:

    def __init__(self):

        self.nodes = {}
        self.edges = {}


    def add_node(self, id:str, node:ElementType=None):
        self.nodes[id] = node
        
    def add_edge(self, source:str, target:str, label:str=None):

        
        if (source not in self.nodes):
            raise Exception(f"Source node not found: {source}")
        
        if (target not in self.nodes):
            raise Exception(f"Target node not found: {target}")

        if source not in self.edges:
            self.edges[source] = {}

        self.edges[source][target] = label


    def dump(self):

        print("Nodes: ")
        if self.nodes:
            print(",".join(self.nodes) + "\n")
        else:
            print("<none>")
        print("Edges:")
        if self.edges:
            for id_source,edges in self.edges.items():
                for id_target,label in edges.items():
                    print(f"{id_source} -({label})-> {id_target}")
        else:
            print("<none>")

"""
Return a pair (rei, closure) denoting:
- rei : a regular expression with interleaving, of type REI
- closure : the "most recent" opening gateway (that must be "closed"), in order to have
            a well-balanced BPMN choreography diagram
"""
def ChoToRei(cho:Choreography, handle_task=None, node:ElementType=None, match:ElementType=None):
    import rei

    atoms = {}

    if node is None:
        rei_head = rei.Start()

        assert len(cho.startEvents) == 1
        node = cho.startEvents[0]

        expect_node_type(cho, node, "START")

        cho_start = cho.startEvents[0]
        cho_next = cho.next(cho_start)

        rei_rest = None
        closure = None

        if len(cho_next) == 0:
            rei_rest = rei.End()
        elif len(cho_next) == 1:
            rei_rest, closure = ChoToRei(cho, handle_task, cho_next[0], match)
        else:
            raise Exception(f"Too many successors: {cho_next}. Expected zero or one.")

        if rei_rest:
            return rei.Conc(rei_head, rei_rest), closure
        else:
            return rei_head, closure
    
    else:
        node_type = cho.node_type(node)

        if node_type == "END":
            return rei.End(), None

        elif node_type == "TASK":
            if handle_task is None:
                handle_task = lambda cho,node: rei.Symbol(node.attrib["name"])

            rei_head = handle_task(cho,node)
            cho_next = cho.next(node)

            rei_rest = None
            closure = None

            if len(cho_next) == 0:
                rei_rest = rei.End()
            elif len(cho_next) == 1:
                rei_rest, closure = ChoToRei(cho, handle_task, cho_next[0], match)
            else:
                raise Exception(f"Too many successors: {cho_next}. Expected zero or one.")

            if rei_rest:
                return rei.Conc(rei_head, rei_rest), closure
            else:
                return rei_head, closure

        elif node_type == "GW_EX_OPEN":
            branches = []
            cho_next = cho.next(node)

            gw_closure = None
            for curr in cho_next:
                rei_branch, closure = ChoToRei(cho, handle_task, curr, node)
                expect_node_type(cho, closure, [ None, "GW_EX_CLOSE" ])
                assert gw_closure is None or gw_closure == closure
                gw_closure = closure
    
                if rei_branch:
                    branches.append(rei_branch)

            rei_head = rei.Union(*branches)

            rei_rest = None
            match_rest = None

            if gw_closure:
                assert len(cho.next(gw_closure)) == 1
                rei_rest, match_rest = ChoToRei(cho, handle_task, cho.next(gw_closure)[0], match)

            if rei_rest:
                return rei.Conc(rei_head, rei_rest), match_rest
            else:
                return rei_head, match_rest

        elif node_type == "GW_PAR_OPEN":
            branches = []
            cho_next = cho.next(node)

            gw_closure = None
            for curr in cho_next:
                rei_branch, closure = ChoToRei(cho, handle_task, curr, node)
                expect_node_type(cho, closure, ["GW_PAR_CLOSE",None])
                assert gw_closure is None or gw_closure == closure
                gw_closure = closure
                
                if rei_branch:
                    branches.append(rei_branch)


            rei_head = rei.Par(*branches)
            
            rei_rest = None
            match_rest = None

            if gw_closure:
                assert len(cho.next(gw_closure)) == 1

                rei_rest, match_rest = ChoToRei(cho, handle_task, cho.next(gw_closure)[0], match)

            if rei_rest:
                return rei.Conc(rei_head, rei_rest), match_rest
            else:
                return rei_head, match_rest

        elif node_type == "GW_INC_OPEN":
            branches = []
            cho_next = cho.next(node)

            gw_closure = None
            for curr in cho_next:
                rei_branch, closure = ChoToRei(cho, handle_task, curr, node)
                expect_node_type(cho, closure, ["GW_INC_CLOSE",None])
                assert gw_closure is None or gw_closure == closure
                gw_closure = closure
                
                if rei_branch:
                    rei_branch = rei.Union(rei.Epsilon(), rei_branch)
                    branches.append(rei_branch)


            rei_head = rei.Par(*branches) 
            rei_rest = None
            match_rest = None

            if gw_closure:
                assert len(cho.next(gw_closure)) == 1

                rei_rest, match_rest = ChoToRei(cho, handle_task, cho.next(gw_closure)[0], match)

            if rei_rest:
                return rei.Conc(rei_head, rei_rest), match_rest
            else:
                return rei_head, match_rest


        elif node_type in [ "GW_PAR_CLOSE", "GW_EX_CLOSE", "GW_INC_CLOSE" ]:
            return None, node

        else:
            raise Exception(f"Node type not handle {node_type}. Node: {node}. Node tag: {node.tag}.  Node name: {node.attrib.get('name')}. Node id: {node.attrib.get('id')}.")

def render_receive (cho:Choreography, node:ElementType):
    print(f"Choreography: {cho}")
    print(f"Node: {node} : {node.attrib['id']} : {node.attrib.get('name')}")
    messages = cho.messages(node)

    symbol = node.attrib["id"]
    if len(messages) > 0:
        initiator = cho.initiator(node)
        recipients = cho.recipients(node)

        assert len(recipients) == 1
        target = recipients[0].attrib["name"].replace(" ", "_")
        msg = messages[0].replace(" ","_")
        symbol = f"{target}?{msg}"

    return Symbol(symbol)