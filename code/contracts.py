from codeop import Compile


class Compileable(object):

    def compile(self):
        raise Exception("Not implemented yet")


class Variable(Compileable):

    def __init__(self, name : str, type : str):
        self._name : str = name
        self._type : str = type

    @property
    def name(self) -> str:
        return self._name

    @property
    def type(self) -> str:
        return self._type

    def compile(self) -> str:
        return f"{self._type} {self._name};"


class Function(Compileable):

    def __init__(self, name : str, parameters : list, body : str, visibility : str):
        self._name : str = name
        self._parameters : list = parameters
        self._body : str = body
        self._visibility : str = visibility

    @property
    def name(self) -> str:
        return self._name

    @property
    def body(self) -> str:
        return self._body

    @property
    def parameters(self) -> list:
        return self._parameters

    @property
    def visibility(self) -> str:
        return self._visibility

    def compile(self):
        parameters_text = ", ".join(map(lambda p: p.compile(), self.parameters))
        return f"""
function {self._name}({parameters_text}) {self._visibility} {{
    {self._body}
}}
        """
    

class Contract(Compileable):

    def __init__(self, name):
        self._name = name
        self._functions : dict = {}
        self._attributes : dict = {}

    @property
    def name(self):
        return self._name

    @property
    def attributes(self) -> list:
        return self._attributes.items()

    @property
    def functions(self) -> list:
        return self._functions.items()

    def add_function(self, f : Function):
        if f.name in self._functions:
            raise Exception(f"Function named {f.name} already exists")
            
        self._functions[f.name] = f

    def add_attribute(self, a : Variable):
        if a.name in self._attributes:
            raise Exception(f"An attribute with name {a.name} already exists")

        self._attributes[a.name] = a

    def compile(self):
        attributes_text = ";\n".join(map(lambda a: a.compile(), self.attributes))
        functions_text = "\n".join(map(lambda f: f.compile(), self.functions))

        return f"""
contract {self._name} {{
    {attributes_text}

    {functions_text}
}}        
        """