from asyncio import events
from codeop import Compile
from re import S
import solcx
from django.conf import settings
import os
import json
import shutil
import datetime
import requests


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

class Event(Compileable):
    def __init__(self, name: str, variables : list):
        self._name : str = name
        self._variables : list = variables
    
    @property
    def name(self) -> str:
        return self._name
    
    @property
    def variables(self) -> list:
        return self._variables

    def compile(self):
        variables_text = ", ".join(map(lambda v: v.compile(), self.variables))
        return f"event {self.name}({variables_text})"

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

    def __init__(self, name):#, version):
        self._name = name
        self._functions : dict = {}
        self._attributes : dict = {}
        self._constructor : dict = {}
        self._directives = []
        self._events : dict = {}
        #self._version = version
        #self._imports = []
        #self._libraries = []

    @property
    def name(self):
        return self._name

    """@property
    def version(self):
        return self._version"""

    @property
    def attributes(self) -> list:
        return self._attributes.items()

    @property
    def functions(self) -> list:
        return self._functions.items()

    @property
    def constructor(self) -> list:
        return self._constructor.items()
    
    """@property
    def imports(self):
        return self._imports"""
    
    """@property
    def libraries(self):
        return self._libraries"""
    
    @property
    def directives(self):
        return self._directives

    @property
    def events(self):
        return self._events

    def add_function(self, f : Function):
        #if f.name in self._functions:
        #    raise Exception(f"Function named {f.name} already exists")
            
        self._functions[f.name] = f

    def add_attribute(self, a : Variable):
        if a.name in self._attributes:
            raise Exception(f"An attribute with name {a.name} already exists")

        self._attributes[a.name] = a

    def add_constructor(self, c : Constructor):
        if len(self._constructor) > 0:
            raise Exception(f"Constructor already exists in the contract")
        
        self._constructor["constructor"] = c

    """def add_import(self, i : str):
        self._imports.append(i)

    def add_library(self, l : str):
        self._libraries.append(l)"""
    
    def add_directive(self, d : str):
        self._directives.append(d)

    def add_event(self, e : Event):
        if e.name in self._events:
            raise Exception(f"An event with name {e.name} already exists")
        self._events[e.name] = e        

    def compile(self):
        #imports_text = "\n".join(map(lambda i: f"import '{i}';", self._imports))
        #libraries_text = "\n".join(map(lambda l: f"{l}", self._libraries))
        directives_text = "\n".join(map(lambda d: f"{d};", self._directives))
        
        attributes_text = "\n".join(map(lambda a: a.compile()+";", self._attributes.values()))
        events_text = "\n".join(map(lambda e: e.compile()+";", self._events.values()))
        functions_text = "\n".join(map(lambda f: f.compile()+"\n", self._functions.values()))
        constructor_text = "\n".join(map(lambda c: c.compile()+"\n", self._constructor.values()))

        directives_text = self.formatText(directives_text)
        attributes_text = self.formatText(attributes_text)
        events_text = self.formatText(events_text)
        functions_text = self.formatText(functions_text)
        constructor_text = self.formatText(constructor_text)

        contract_text = f"""contract {self._name} {{
{directives_text}

{events_text}

{attributes_text}

{constructor_text}

{functions_text}
}}  
"""
        """compiled_sol = solcx.compile_source(contract_text,
                             #output_values = ["abi","bin-runtime","metadata"],
                             solc_version = "0.8.0",
                             output_dir = f"{settings.BASE_DIR}\..\public\contracts",
                             overwrite=True
        )
        compiled_sol = solcx.compile_standard(
            {
                "language": "Solidity",
                "sources": 
                    {
                        f"{self.name}.sol": 
                            {
                                "content": contract_text
                            }
                    },
                "settings": {
                    "outputSelection": {
                        "*": {"*": ["abi", "metadata", "evm.bytecode", "evm.sourceMap"]}
                    },
                    #"libraries": {"strings.sol"}
                },
            },
            solc_version = "0.8.0",
            allow_paths = ["."]
            
        )
        with open("compiled_sol.json", "w") as file:
            json.dump(compiled_sol, file)

        os.rename("compiled_sol.json",f"{self.name}_compiled_sol.json")
        
        try:
            smartContract_file = open(f"{settings.BASE_DIR}\..\public\contracts\{self.name}.sol","w")
            try: 
                smartContract_file.write(contract_text)
                if (os.path.exists(f"{settings.BASE_DIR}\..\public\contracts\{self.name}_compiled_sol.json")):
                    os.remove(f"{settings.BASE_DIR}\..\public\contracts\{self.name}_compiled_sol.json")
                    #os.rename(f"{settings.BASE_DIR}\..\public\contracts\combined.json",f"{settings.BASE_DIR}\..\public\contracts\{self.name}_combined.json")
                #else:
                #    os.rename(f"{settings.BASE_DIR}\..\public\contracts\combined.json",f"{settings.BASE_DIR}\..\public\contracts\{self.name}_combined.json")
                shutil.move(f"{self.name}_compiled_sol.json",f"{settings.BASE_DIR}\..\public\contracts\{self.name}_compiled_sol.json")
            except Exception as err:
                print("Something went wrong when writing to the file: ", err)
            finally:
                smartContract_file.close()
        except:
            print("Something went wrong when opening the file")
        
        return compiled_sol"""
        return contract_text

class SmartContract(Compileable):
    
    def __init__(self, version: str):
        self._version = version
        self._imports = []
        self._libraries : dict = {}
        self._contracts : dict = {}

    @property
    def version(self):
        return self._version

    @property
    def imports(self):
        return self._imports
    
    @property
    def libraries(self):
        return self._libraries

    @property
    def contracts(self):
        return self._contracts

    def add_import(self, i : str):
        self._imports.append(i)

    def add_library(self, name: str, url : str):
        if name in self.libraries:
            raise Exception(f"A library with name {name} already exists")
        self._libraries[name] = '\n'.join(str(line) for line in requests.get(url).text.splitlines()[38::])

    def add_contract(self, c : Contract):
        if c.name in self._contracts:
            raise Exception(f"A contract with name {c.name} already exists")
        self._contracts[c.name] = c

    def compile(self, debug : bool):
        imports_text = "\n".join(map(lambda i: f"import '{i}';", self._imports))
        libraries_text = "\n".join(map(lambda l: l+"\n", self.libraries.values()))
        contracts_text = "\n".join(map(lambda c: c.compile()+"\n", self.contracts.values())) 
        
        smart_contract_text = f"""pragma solidity >= {self._version};
pragma abicoder v2;
{imports_text}

{libraries_text}

{contracts_text}
"""
        compiled_sol = solcx.compile_standard(
            {
                "language": "Solidity",
                "sources": 
                    {
                        f"smart_contract.sol": 
                            {
                                "content": smart_contract_text
                            }
                    },
                "settings": {
                    "outputSelection": {
                        "*": {"*": ["abi", "metadata", "evm.bytecode", "evm.sourceMap"]}
                    },
                    #"libraries": {"strings.sol"}
                },
            },
            solc_version = "0.8.0",
            allow_paths = ["."]
        )
        if (debug):
            file_name = "_".join(["smart_contract",datetime.datetime.now().strftime("%y%m%d_%H%M%S")])
            tmp_path = f"{settings.BASE_DIR}\..\public\\tmp\{file_name}.sol"
            with open(tmp_path,"w") as file:
                file.write(smart_contract_text)
                print("\nSmart contract saved at: ",tmp_path,"\n")
        """with open("compiled_sol.json", "w") as file:
            json.dump(compiled_sol, file)

        os.rename("compiled_sol.json",f"smart_contract_compiled_sol.json")
        
        try:
            smartContract_file = open(f"{settings.BASE_DIR}\..\public\contracts\smart_contract.sol","w")
            try: 
                smartContract_file.write(smart_contract_text)
                if (os.path.exists(f"{settings.BASE_DIR}\..\public\contracts\smart_contract_compiled_sol.json")):
                    os.remove(f"{settings.BASE_DIR}\..\public\contracts\smart_contract_compiled_sol.json")
                    #os.rename(f"{settings.BASE_DIR}\..\public\contracts\combined.json",f"{settings.BASE_DIR}\..\public\contracts\{self.name}_combined.json")
                #else:
                #    os.rename(f"{settings.BASE_DIR}\..\public\contracts\combined.json",f"{settings.BASE_DIR}\..\public\contracts\{self.name}_combined.json")
                shutil.move(f"smart_contract_compiled_sol.json",f"{settings.BASE_DIR}\..\public\contracts\smart_contract_compiled_sol.json")
            except Exception as err:
                print("Something went wrong when writing to the file: ", err)
            finally:
                smartContract_file.close()
        except:
            print("Something went wrong when opening the file")"""
        return compiled_sol




        

        
