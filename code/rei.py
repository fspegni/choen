class REI:

    def __str__(self):
        return ""


class Symbol(REI):

    def __init__(self, symbol):
        self.symbol = symbol


    def __str__(self):
        return self.symbol


class Conc(REI):

    def __init__(self, *items):

        self.items = list(items)
    def __str__(self):
        return " ".join(map(lambda curr: str(curr), self.items))

class Par(REI):

    def __init__(self, *items):
        self.items = list(items)

    def __str__(self):
        return "(" + " & ".join(map(lambda curr: str(curr), self.items)) + ")"

class Union(REI):

    def __init__(self, *items):
        self.items = list(items)

    def __str__(self):
        return "(" + " | ".join(map(lambda curr: str(curr), self.items)) + ")"



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