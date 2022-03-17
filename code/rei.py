class REI:

    def __str__(self):
        return ""


    def __bytes__(self):
        return str(self).encode('utf-8')

    @property
    def latex(self):
        return ""




class Symbol(REI):

    def __init__(self, symbol):
        self.symbol = symbol

    def __str__(self):
        res = self.symbol

        if " " in res or not res:
            res = f"'{res}'"
    
        return res

    @property
    def latex(self):
        return f"\\textit{{{self.symbol}}}"


class Conc(REI):

    def __init__(self, *items):

        self.items = list(items)

    def __str__(self):
        return " ".join(map(lambda curr: str(curr), self.items))

    @property
    def latex(self):
        return " \\cdot ".join(map(lambda curr: curr.latex if curr else "", self.items))


class Par(REI):

    def __init__(self, *items):
        self.items = list(items)

    def __str__(self):
        return "(" + " & ".join(map(lambda curr: str(curr), self.items)) + ")"

    @property
    def latex(self):
        return "(" + " \& ".join(map(lambda curr: curr.latex if curr else "", self.items)) + ")"


class Union(REI):

    def __init__(self, *items):
        self.items = list(items)

    def __str__(self):
        return "(" + " | ".join(map(lambda curr: str(curr), self.items)) + ")"

    @property
    def latex(self):
        return "(" + " \\vert ".join(map(lambda curr: curr.latex if curr else "", self.items)) + ")"


class NFA:

    def __init__(self):

        self.nodes = {}
        self.edges = {}


    def add_node(self, id, node=None):
        self.nodes[id] = node
        
    def add_edge(self, source, target, label=None):

        
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


def ChoToRei(cho, node=None, match=None):
    import rei

    atoms = {}

    if not node:
        # begin

        rei_head = rei.Symbol("start")


        assert len(cho.startEvents) == 1
        node = cho.startEvents[0]
        node_type = cho.node_type(node)
        assert node_type == "START", f"Node: {node}. Tag: {node.tag}. Type: {node_type}"

        print(f"Node: {node} - Type: {node_type}")


        cho_start = cho.startEvents[0]
        cho_next = cho.next(cho_start)

        assert len(cho_next) == 1
        
        rei_rest, closure = ChoToRei(cho, cho_next[0], match)

        if rei_rest:
            return rei.Conc(rei_head, rei_rest), closure
        else:
            return rei_head, closure
    
    else:
        node_type = cho.node_type(node)
        # print(f"Node: {node} - Type: {node_type}")

        if node_type == "END":
            return rei.Symbol("end"), None

        elif node_type == "TASK":
            rei_head = rei.Symbol(node.attrib["name"])
            cho_next = cho.next(node)

            assert len(cho_next) == 1
            
            rei_rest, closure = ChoToRei(cho, cho_next[0], match)

            if rei_rest:
                return rei.Conc(rei_head, rei_rest), closure
            else:
                return rei_head, closure
            # return rei.Conc(rei_head, rei_rest), closure

        elif node_type == "GW_EX_OPEN":
            branches = []
            cho_next = cho.next(node)

            gw_closure = None
            for curr in cho_next:
                rei_branch, closure = ChoToRei(cho, curr, node)
                assert cho.node_type(closure) == "GW_EX_CLOSE", f"Node: {closure} - Type: {cho.node_type(closure)}"
                assert not gw_closure or gw_closure == closure
                gw_closure = closure
    
                if rei_branch:
                    branches.append(rei_branch)

            assert gw_closure != None
            assert len(cho.next(gw_closure)) == 1

            rei_head = rei.Union(*branches)

            rei_rest, match_rest = ChoToRei(cho, cho.next(gw_closure)[0], match)

            if rei_rest:
                return rei.Conc(rei_head, rei_rest), match_rest
            else:
                return rei_head, match_rest

        elif node_type == "GW_PAR_OPEN":
            branches = []
            cho_next = cho.next(node)

            gw_closure = None
            for curr in cho_next:
                rei_branch, closure = ChoToRei(cho, curr, node)
                assert cho.node_type(closure) == "GW_PAR_CLOSE"
                assert not gw_closure or gw_closure == closure
                gw_closure = closure
                
                if rei_branch:
                    branches.append(rei_branch)


            assert gw_closure != None
            assert len(cho.next(gw_closure)) == 1

            rei_head = rei.Par(*branches)
            
            rei_rest, match_rest = ChoToRei(cho, cho.next(gw_closure)[0], match)

            if rei_rest:
                return rei.Conc(rei_head, rei_rest), match_rest
            else:
                return rei_head, match_rest

        elif node_type == "GW_INC_OPEN":
            branches = []
            cho_next = cho.next(node)

            gw_closure = None
            for curr in cho_next:
                rei_branch, closure = ChoToRei(cho, curr, node)
                assert cho.node_type(closure) == "GW_INC_CLOSE"
                assert not gw_closure or gw_closure == closure
                gw_closure = closure
                
                if rei_branch:
                    rei_branch = rei.Union(rei.Symbol(''), rei_branch)
                    branches.append(rei_branch)

            assert gw_closure != None
            assert len(cho.next(gw_closure)) == 1

            rei_head = rei.Par(*branches) 

            rei_rest, match_rest = ChoToRei(cho, cho.next(gw_closure)[0], match)

            if rei_rest:
                return rei.Conc(rei_head, rei_rest), match_rest
            else:
                return rei_head, match_rest


        elif node_type in [ "GW_PAR_CLOSE", "GW_EX_CLOSE", "GW_INC_CLOSE" ]:
            return None, node

        else:
            raise Exception(f"Node type not handle {node_type}. Node: {node}. Node tag: {node.tag}.  Node name: {node.attrib.get('name')}. Node id: {node.attrib.get('id')}.")