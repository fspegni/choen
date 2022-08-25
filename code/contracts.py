from codeop import Compile
import solcx
from django.conf import settings

class Compileable(object):

    def compile(self):
        raise Exception("Not implemented yet")

    def formatText(self, body: str) -> str:
        body = body.split('\n')
        formatted_body = []
        for line in body:
            line = '\t' + line
            formatted_body.append(line) 
        formatted_body = '\n'.join(formatted_body)
        return formatted_body


class Variable(Compileable):

    def __init__(self, name : str, type : str, location : str = "", value : str = ""):
        self._name : str = name
        self._type : str = type
        self._location : str = location
        self._value : object = value

    @property
    def name(self) -> str:
        return self._name

    @property
    def type(self) -> str:
        return self._type

    @property
    def location(self) -> str:
        return self._location
    
    @property
    def value(self) -> str:
        return self._value

    def compile(self) -> str:
        if (self._location == "" and self._value == ""):
            return f"{self._type} {self._name}"
        elif (self._location == "" and self._value != ""):
            return f"{self._type} {self._name} = {self._value}"
        elif (self._location != "" and self._value == ""):
            return f"{self._type} {self._location} {self._name}"
        else:
            return f"{self._type} {self._location} {self._name} = {self._value}"

class Function(Compileable):

    def __init__(self, name : str, parameters : list, body : str, visibility : str, returns : str = ""):
        self._name : str = name
        self._parameters : list = parameters
        self._body : str = self.formatText(body)
        self._visibility : str = visibility
        self._returns : str = returns

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

    @property
    def returns(self) -> str:
        return self._returns

    def compile(self):
        parameters_text = ", ".join(map(lambda p: p.compile(), self.parameters))
        if (self._returns == ""):
            return f"""function {self._name}({parameters_text}) {self._visibility} {{
{self._body}
}}
"""
        else:
            return f"""function {self._name}({parameters_text}) {self._visibility} returns ({self._returns}){{
{self._body}
}}
"""


class Constructor(Function):

    def __init__(self, parameters : list, body : str, visibility : str = "public"):
        super().__init__("constructor", parameters, body, visibility)

    def compile(self):
        parameters_text = ", ".join(map(lambda p: p.compile(), self.parameters))
        return f"""{self._name}({parameters_text}) {self._visibility} {{
{self._body}
}}
"""


class Contract(Compileable):

    def __init__(self, name, version):
        self._name = name
        self._version = version
        self._functions : dict = {}
        self._attributes : dict = {}
        self._constructor : dict = {}

    @property
    def name(self):
        return self._name

    @property
    def version(self):
        return self._version

    @property
    def attributes(self) -> list:
        return self._attributes.items()

    @property
    def functions(self) -> list:
        return self._functions.items()

    @property
    def constructor(self) -> list:
        return self._constructor.items()

    def add_function(self, f : Function):
        if f.name in self._functions:
            raise Exception(f"Function named {f.name} already exists")
            
        self._functions[f.name] = f

    def add_attribute(self, a : Variable):
        if a.name in self._attributes:
            raise Exception(f"An attribute with name {a.name} already exists")

        self._attributes[a.name] = a

    def add_constructor(self, c : Constructor):
        if len(self._constructor) > 0:
            raise Exception(f"Constructor already exists in the contract")
        
        self._constructor["constructor"] = c

    def compile(self):
        attributes_text = "\n".join(map(lambda a: a.compile()+";", self._attributes.values()))
        functions_text = "\n".join(map(lambda f: f.compile()+"\n", self._functions.values()))
        constructor_text = "\n".join(map(lambda c: c.compile()+"\n", self._constructor.values()))

        attributes_text = self.formatText(attributes_text)
        functions_text = self.formatText(functions_text)
        constructor_text = self.formatText(constructor_text)

        contract_text = f"""
pragma solidity >= {self._version};
pragma abicoder v2;

contract {self._name} {{

{attributes_text}

{constructor_text}

{functions_text}
}}  
"""
        solcx.compile_source(contract_text,
                             output_values = ["abi","bin-runtime"],
                             solc_version = "0.7.6",
                             output_dir = f"{settings.BASE_DIR}\..\public\contracts",
        )

        try:
            smartContract_file = open(f"{settings.BASE_DIR}\..\public\contracts/{self.name}.sol","w")
            try:
                smartContract_file.write(contract_text)
            except:
                print("Something went wrong when writing to the file")
            finally:
                smartContract_file.close()
        except:
            print("Something went wrong when opening the file")