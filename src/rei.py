from bpmn_parser.models import Choreography, ElementType
#from mpst.models import MPST, GlobalType
import re

def sanitize(text):

    return re.sub(r"[^a-zA-Z0-9]", "_", text)
    #return text.replace(" ", "_").replace("-", "_").replace("/", "_").replace("&", "_").replace(",","_").replace("(","_").replace(")","_")

def expect_node_type(cho:Choreography, node:ElementType, ntypes, limit_node=None):

    if isinstance(ntypes, str):
        ntypes = [ ntypes] 

    real_ntype = cho.node_type(node, limit_node)

    #if real_ntype not in ntypes:
    #    breakpoint()
    assert real_ntype in ntypes, f"Expected node of type '{ntypes}'. Found: Node: {node} - Type: {real_ntype}"


class REI:

    def __str__(self):
        return ""


    def __bytes__(self):
        return str(self).encode('utf-8')

    @property
    def latex(self):
        return ""

    def contains(self, rei):
        return self == rei

    def rtrim(self):
        return self

    def ltrim(self):
        return self


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

    def contains(self, rei):
        return isinstance(rei, Symbol) and rei.symbol == self.symbol


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

    def contains(self, rei):
        return isinstance(rei, Start) or (isinstance(rei, type) and rei == Start)


class End(Symbol):

    def __init__(self):
        self.symbol = "$"

    @property
    def latex(self):
        return f"\\$"        

    def contains(self, rei):
        return isinstance(rei, End) or (isinstance(rei, type) and rei == End)


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

    def contains(self, rei):

        if isinstance(rei, Star) and self.rei == rei.rei:
            return True
        else:
            return self.rei.contains(rei)
    

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

    def contains(self, rei):
        #breakpoint()
        if not self.items:
            return False

        if isinstance(rei, Conc) and self.items == rei.items:
            return True
        else:
            for curr in self.items:
                if curr.contains(rei):
                    return True

            return False

    def ltrim(self):
        if isinstance(self.items[0], Start):
            self.items = self.items[1:]

    def rtrim(self):
        if isinstance(self.items[-1], End):
            self.items.pop()


class Par(REI):

    def __init__(self, *items):
        self.items = list(map(lambda curr: Symbol(curr) if isinstance(curr, str) else curr, items))

    def __str__(self):
        return "(" + " & ".join(map(lambda curr: str(curr), self.items)) + ")"

    @property
    def latex(self):
        return "(" + " \& ".join(map(lambda curr: curr.latex if curr else "", self.items)) + ")"

    def contains(self, rei):

        if isinstance(rei, Par) and self.items == rei.items:
            return True
        else:
            for curr in self.items:
                if curr.contains(rei):
                    return True

            return False


class Union(REI):

    def __init__(self, *items):
        self.items = list(map(lambda curr: Symbol(curr) if isinstance(curr, str) else curr, items))

    def __str__(self):
        return "(" + " | ".join(map(lambda curr: str(curr), self.items)) + ")"

    @property
    def latex(self):
        return "(" + " \\vert ".join(map(lambda curr: curr.latex if curr else "", self.items)) + ")"

    def contains(self, rei):

        if isinstance(rei, Union) and self.items == rei.items:
            return True
        else:
            for curr in self.items:
                if curr.contains(rei):
                    return True

            return False



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
def ChoToRei(cho:Choreography, handle_task=None, node:ElementType=None, match:ElementType=None, limit_node:ElementType=None):
    import rei

    #breakpoint()
    atoms = {}

    if node is None:
        rei_head = rei.Start()

        assert len(cho.startEvents) == 1
        node = cho.startEvents[0]

        expect_node_type(cho, node, "START", limit_node)

        cho_start = cho.startEvents[0]
        cho_next = cho.next(cho_start, limit_node)

        rei_rest = None
        closure = limit_node # was: None

        if len(cho_next) == 0:
            rei_rest = rei.End()
        elif len(cho_next) == 1:
            rei_rest, closure = ChoToRei(cho, handle_task, cho_next[0], match, limit_node)
        else:
            raise Exception(f"Too many successors: {cho_next}. Expected zero or one.")

        if rei_rest:
            rei_head.rtrim()
            rei_rest.ltrim()
            return rei.Conc(rei_head, rei_rest), closure
        else:
            return rei_head, closure
    
    else:
        node_type = cho.node_type(node, limit_node)

        if node_type == "END":
            return rei.End(), limit_node # was: None

        elif node_type == "TASK":
            if handle_task is None:
                handle_task = lambda cho,node: rei.Symbol(node.attrib["name"])

            rei_head = handle_task(cho,node)
            cho_next = cho.next(node, limit_node)

            rei_rest = None
            closure = limit_node # was: None

            if len(cho_next) == 0:
                rei_rest = rei.End()
            elif len(cho_next) == 1:
                rei_rest, closure = ChoToRei(cho, handle_task, cho_next[0], match, limit_node)
            else:
                raise Exception(f"Too many successors: {cho_next}. Expected zero or one.")

            if rei_rest:
                rei_head.rtrim()
                rei_rest.ltrim()
                return rei.Conc(rei_head, rei_rest), closure
            else:
                return rei_head, closure

        elif node_type == "GW_EX_OPEN":
            #breakpoint()
            branches = []
            cho_next = cho.next(node, limit_node)

            gw_closure = None
            for curr in cho_next:
                rei_branch, closure = ChoToRei(cho, handle_task, curr, node, limit_node)
                expect_node_type(cho, closure, [ None, "GW_EX_CLOSE" ], limit_node)
                assert gw_closure is None or gw_closure == closure
                gw_closure = closure
    
                if rei_branch:
                    branches.append(rei_branch)

            rei_head = rei.Union(*branches)

            rei_rest = None
            match_rest = limit_node # was: None

            if gw_closure:
                gw_closure_next = cho.next(gw_closure, limit_node)
                #assert len(cho.next(gw_closure, limit_node)) == 1
                assert len(gw_closure_next) == 1
                #rei_rest, match_rest = ChoToRei(cho, handle_task, cho.next(gw_closure)[0], match, limit_node)
                rei_rest, match_rest = ChoToRei(cho, handle_task, gw_closure_next[0], match, limit_node)

            if rei_rest:
                rei_head.rtrim()
                rei_rest.ltrim()

                return rei.Conc(rei_head, rei_rest), match_rest
            else:
                return rei_head, match_rest

        elif node_type == "GW_EX_LOOP_OPEN":
            #breakpoint()
            #raise Exception("I'm going to deal with it in a short while")
            branches = []
            cho_next = cho.next(node, limit_node)

            # put in new_limit_node the closing exclusive gateway for this loop
            reachable_from_node = cho.reachable(node, limit_node)
            new_limit_node = None
            for curr in cho.prev(node):
                if curr in reachable_from_node:
                    new_limit_node = curr
                    break
            assert new_limit_node is not None

            gw_closure = None
            for curr in cho_next:
                rei_branch, closure = ChoToRei(cho, handle_task, curr, node, new_limit_node) # NOTE: the current node (of type GW_EX_LOOP_OPEN) becomes the limit_node for the ChoToRei translation applied on the current branch

                #print(f"CHOTOREI: {node.attrib['id']} : branch: {str(rei_branch)} : closure = {closure}")
                #expect_node_type(cho, closure, [ "GW_EX_LOOP_CLOSE" ], new_limit_node)
                assert closure == new_limit_node # this replaces the expect_node_type 
                assert gw_closure is None or gw_closure == closure
                gw_closure = closure
    
                if rei_branch:
                    branches.append(rei_branch)

            if len(branches) == 1:
                branches[0].rtrim()
                rei_head = rei.Star(branches[0])
            else:
                for b in branches:
                    b.rtrim()
                rei_head = rei.Star(rei.Union(*branches))

            rei_rest = None
            match_rest = limit_node # was: None

            if gw_closure:
                gw_closure_next = cho.next(gw_closure, limit_node)
                gw_closure_next.remove(node) # in the case of a loop, the gw_closure points back to the beginning of the loop, thus we have to remove it
                assert len(gw_closure_next) == 1
                #assert len(cho.next(gw_closure)) == 1
                #rei_rest, match_rest = ChoToRei(cho, handle_task, cho.next(gw_closure)[0], match, limit_node)
                rei_rest, match_rest = ChoToRei(cho, handle_task, gw_closure_next[0], match, limit_node)
            #if rei_rest:
            #    return rei.Conc(rei_head, rei_rest), match_rest
            #else:
            #    return rei_head, match_rest

            assert rei_rest != None

            rei_head.rtrim()
            rei_rest.ltrim()

            return rei.Conc(rei_head, rei_rest), match_rest

        elif node_type == "GW_PAR_OPEN":
            branches = []
            cho_next = cho.next(node, limit_node)

            gw_closure = None
            for curr in cho_next:
                rei_branch, closure = ChoToRei(cho, handle_task, curr, node, limit_node)
                expect_node_type(cho, closure, ["GW_PAR_CLOSE",None], limit_node)
                assert gw_closure is None or gw_closure == closure
                gw_closure = closure
                
                if rei_branch:
                    branches.append(rei_branch)


            rei_head = rei.Par(*branches)
            
            rei_rest = None
            match_rest = limit_node # was: None

            if gw_closure:
                gw_closure_next = cho.next(gw_closure, limit_node)

                assert len(gw_closure_next) == 1, f"Expected one gw_closure_next for {gw_closure}. Found: {gw_closure_next}"
                #rei_rest, match_rest = ChoToRei(cho, handle_task, cho.next(gw_closure)[0], match, limit_node)
                rei_rest, match_rest = ChoToRei(cho, handle_task, gw_closure_next[0], match, limit_node)

            if rei_rest:

                rei_head.rtrim()
                rei_rest.ltrim()

                return rei.Conc(rei_head, rei_rest), match_rest
            else:
                return rei_head, match_rest

        elif node_type == "GW_INC_OPEN":
            branches = []
            cho_next = cho.next(node, limit_node)

            gw_closure = None
            for curr in cho_next:
                rei_branch, closure = ChoToRei(cho, handle_task, curr, node, limit_node)
                expect_node_type(cho, closure, ["GW_INC_CLOSE",None], limit_node)
                assert gw_closure is None or gw_closure == closure, f"gw_closure ({gw_closure}) != closure ({closure})"
                gw_closure = closure
                
                if rei_branch:
                    rei_branch = rei.Union(rei.Epsilon(), rei_branch)
                    branches.append(rei_branch)


            rei_head = rei.Par(*branches) 
            rei_rest = None
            match_rest = limit_node # was: None

            if gw_closure:
                gw_closure_next = cho.next(gw_closure, limit_node)
                assert len(gw_closure_next) == 1
                #assert len(cho.next(gw_closure)) == 1

                #rei_rest, match_rest = ChoToRei(cho, handle_task, cho.next(gw_closure)[0], match, limit_node)
                rei_rest, match_rest = ChoToRei(cho, handle_task, gw_closure_next[0], match, limit_node)

            #breakpoint()

            if rei_rest:

                rei_head.rtrim()
                rei_rest.ltrim()

                return rei.Conc(rei_head, rei_rest), match_rest
            else:
                return rei_head, match_rest

        elif node_type in [ "GW_PAR_CLOSE", "GW_EX_CLOSE", "GW_EX_LOOP_CLOSE", "GW_INC_CLOSE" ]:
            return None, node

        else:
            raise Exception(f"Node type not handle {node_type}. Node: {node}. Node tag: {node.tag}.  Node name: {node.attrib.get('name')}. Node id: {node.attrib.get('id')}.")

def render_receive (cho:Choreography, node:ElementType):
#    print(f"Choreography: {cho}")
#    print(f"Node: {node} : {node.attrib['id']} : {node.attrib.get('name')}")
    m_request = None
    m_response = None

#    symbol = node.attrib["id"] 
    res = None

    initiator, recipients = cho.involve(node)
    initiator = sanitize(initiator.attrib["name"])
    recipients = map(lambda curr: sanitize(curr.attrib["name"]), recipients)

    #initiator = sanitize(cho.initiator(node).attrib["name"]) #.replace(" ","_")
    #recipients = cho.recipients(node)
    assert len(recipients) == 1, "At the moment we allow only one recipient per task" # TODO this limitation can be easily overcome: one can introduce the interleaving among all the recipients
    #target = sanitize(recipients[0].attrib["name"]) #.replace(" ", "_")
    target = recipients[0]

    messages = cho.messages(node)

    n_messages = len(messages)
    if n_messages == 2:
        m_request = sanitize(messages[0]) #.replace(" ","_")
        m_response = sanitize(messages[1]) #.replace(" ","_")
        res = Conc(Symbol(f"{target}?{m_request}"), Symbol(f"{initiator}?{m_response}"))
    elif n_messages == 1:
        m_request = sanitize(messages[0]) #.replace(" ","_")
        res = Symbol(f"{target}?{m_request}")
    elif n_messages == 0:
        res = Symbol(node.attrib["id"])
    else:
        raise Exception(f"Condition not accepted: at most 2 messages per tasks are supported. Received: {n_messages}")
    
    return res

def render_send_receive (cho:Choreography, node:ElementType):
#    print(f"Choreography: {cho}")
#    print(f"Node: {node} : {node.attrib['id']} : {node.attrib.get('name')}")
    m_request = None
    m_response = None

    messages = cho.messages(node) 

    res = None
    initiator = sanitize(cho.initiator(node).attrib["name"]) #.replace(" ","_")
    recipients = cho.recipients(node)
    assert len(recipients) == 1, "At the moment we allow only one recipient per task" # TODO this limitation can be easily overcome: one can introduce the interleaving among all the recipients
    target = sanitize(recipients[0].attrib["name"]) #.replace(" ", "_")

    n_messages = len(messages)
    if n_messages == 2:
        #breakpoint()
        m_request = sanitize(messages[0]) #.replace(" ","_")
        m_response = sanitize(messages[1]) #.replace(" ","_")
        #res = Conc(Symbol(f"{target}?{m_request}"), Symbol(f"{initiator}?{m_response}"))
        #res = Conc(Par(Symbol(f"{initiator}!{m_request}"), Symbol(f"{target}?{m_request}")), Par(Symbol(f"{target}!{m_response}"), Symbol(f"{initiator}?{m_response}")))
        res = Conc(Symbol(f"{initiator}!{m_request}"), Symbol(f"{target}?{m_request}"), Symbol(f"{target}!{m_response}"), Symbol(f"{initiator}?{m_response}"))
    elif n_messages == 1:
        m_request = sanitize(messages[0]) #.replace(" ","_")
        #res = Par(Symbol(f"{initiator}!{m_request}"), Symbol(f"{target}?{m_request}"))
        res = Conc(Symbol(f"{initiator}!{m_request}"), Symbol(f"{target}?{m_request}"))
    elif n_messages == 0:
        res = Symbol(node.attrib["id"])
    else:
        raise Exception(f"Condition not accepted: at most 2 messages per tasks are supported. Received: {n_messages}")
    
    return res



##    symbol = node.attrib["id"]
##    if len(messages) > 0:
##        initiator = cho.initiator(node)
##        recipients = cho.recipients(node)
##
##        assert len(recipients) == 1
##        target = recipients[0].attrib["name"].replace(" ", "_")
##        msg = messages[0].replace(" ","_")
##        symbol = f"{target}?{msg}"
##
##    return Symbol(symbol)
        
##def MPSTToRei(mpst:MPST, handle_task=None, node: dict = None):
##    import rei
##
##    if not node:
##
##        print(mpst.root)
##            


class Filter:

    def __init__(self, initiators=None, actions=None, targets=None, messages=None):
        self._initiators = set(initiators or [])
        self._actions = set(actions or [])
        self._targets = set(targets or [])
        self._messages = set(messages or [])
    
    @property
    def initiators(self):
        return self._initiators
    
    @property
    def actions(self):
        return self._actions
    
    @property
    def targets(self):
        return self._targets
    
    @property
    def messages(self):
        return self._messages
    
    def combine(self, f):
    
        if not f:
            raise ValueError("Expected non-empty filter as argument")
    
    
        self._initiators = self._initiators.union(f.initiators)
        self._actions = self._actions.union(f.actions)
        self._targets = self._targets.union(f.targets)
        self._messages = self._messages.union(f.messages)
 
