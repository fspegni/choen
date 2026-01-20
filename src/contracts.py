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
import re

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

class Constant(Variable):


    def __init__(self, name : str, type : str, value : str = ""):
        super().__init__(name, type, value=value)

    def compile(self) -> str:
        init = ""
        if self._value:
            init = f" = {self._value}"
        return f"{self._type} constant {self._name}{init};"

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


class Library(Compileable):

    def __init__(self, name : str):
        self._name : str = name
        self._functions : list = []

    def add_function(self, f : Function):
            
        self._functions.append(f)

    def compile(self):
        function_bodies = "\n".join(map(lambda f: f.compile() + "\n" , self._functions))
        return f"""library {self._name} {{
            {function_bodies}
        }}
        """
    

class Constructor(Function):

    def __init__(self, parameters : list, body : str, visibility : str = "public"):
        super().__init__("constructor", parameters, body, visibility)

    def compile(self):
        parameters_text = ", ".join(map(lambda p: p.compile(), self.parameters))
        return f"""{self._name}({parameters_text}) {{
{self._body}
}}
"""


class Struct(Compileable):

    def __init__(self, name : str, attributes : list):
        self._name = name
        self._attributes = attributes

    @property
    def name(self):
        return self._name

    @property
    def attributes(self):
        return self._attributes


    def compile(self):
        #breakpoint()
        enum_body = "\n    ".join(map(lambda a: f"{a[1]} {a[0]};", self._attributes))
        text = "struct " + self.name + " {\n    " + enum_body + "\n}\n"
        return str(text)


class Enum(Compileable):

    def __init__(self, name : str, values : list, sep="\n    "):
        self._name = name
        self._values = values
        self._sep = sep

    @property
    def name(self):
        return self._name

    @property
    def values(self):
        return self._values

    def compile(self):
        #breakpoint()
        last = len(self.values)-1
        lines = []
        for i,v in enumerate(self.values):
            if i < last:
                lines.append(f"{str(v)}, // {i}") 
            else:
                lines.append(f"{str(v)} // {i}") 

        enum_body = (self._sep).join(lines)
        text = "enum " + self.name + " {\n    " + enum_body + "\n}\n"
        return str(text)

class Contract(Compileable):

    def __init__(self, name):#, version):
        self._name = name
        self._functions : dict = {}
        self._attributes : dict = {}
#        self._structures : dict = {}
        self._constructor : dict = {}
        self._directives = []
        self._events : dict = {}
        self._enums: dict = {}
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

#    @property
#    def structures(self) -> list:
#        return self._structures.items()

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

    def add_enum(self, enum : Enum):
        self._enums[enum.name] = enum

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
     
      
        enums_text = "\n".join(map(lambda a: a.compile(), self._enums.values()))
        struct_text = "" # FS this should be removed
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

{enums_text}

{struct_text}

{attributes_text}

{constructor_text}

{functions_text}
}}  
"""
        """compiled_sol = solcx.compile_source(contract_text,
                             #output_values = ["abi","bin-runtime","metadata"],
                             solc_version = "{settings.SOLC_VERSION}",
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
            solc_version = "{settings.SOLC_VERSION}",
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
        #self._libraries : list = []
        self._functions : list = []
        self._attributes : list = []
        self._libraries : dict = {}
        self._contracts : dict = {}
        self._verbatim : str = ""
        self._enums : dict = {}
        self._structures : dict = {}
        self._types : dict = {}
    

        # information populated after the compilation
        self._compiled_sol = None



    def add_verbatim(self, verbatim):
        self._verbatim = verbatim

    def add_struct(self, s : Struct):
        if s.name in self._structures:
            raise Exception(f"A structure with name {s.name} already exists")

        self._structures[s.name] = s

    def add_type(self, new_type: str, existing_type: str):

        self._types[new_type] = existing_type

    @property
    def structures(self):
        return self._structures.values()

    def add_enum(self, enum : Enum):
        #self._enums.append(enum)
        self._enums[enum.name] = enum

    @property
    def enumerations(self):
        return self._enums.values()

    @property
    def attributes(self):
        return self._attributes

    @property
    def functions(self):
        return self._functions

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

    def add_function(self, f : Function):
        self._functions.append(f)

    def add_attribute(self, v : Variable):
        self._attributes.append(v)

    def add_import(self, i : str):
        self._imports.append(i)

    def add_library(self, name: str, library_or_url : Library | str):
        if name in self.libraries:
            raise Exception(f"A library with name {name} already exists")

        #if isinstance(library_or_url, str):
        #    self._libraries[name] = '\n'.join(str(line) for line in requests.get(library_or_url).text.splitlines()[38::])
        if isinstance(library_or_url, Library):
            self._libraries[name] = library_or_url
        else:
            raise ValueError(f"Library of unknown type. Expected : string or Library. Passed: {library_or_url}")

    def add_contract(self, c : Contract):
        if c.name in self._contracts:
            raise Exception(f"A contract with name {c.name} already exists")
        self._contracts[c.name] = c

    def get_abi(self, contract_name:str):
        if not contract_name:
            raise ValueError("Expected non-empty contract name")

        if not self._compiled_sol:
            raise Exception("You must compile the smart contract before invoking this method")

        return json.loads(self._compiled_sol["contracts"]["smart_contract.sol"][contract_name]["metadata"])["output"]["abi"]


    def get_bytecode(self, contract_name:str, libraries=None):
        if not contract_name:
            raise ValueError("Expected non-empty contract name")

        if not self._compiled_sol:
            raise Exception("You must compile the smart contract before invoking this method")

 
        compiled_sol = self._compiled_sol

        #get bytecode
        bytecode = compiled_sol["contracts"]["smart_contract.sol"][contract_name]["evm"]["bytecode"]["object"]

        if libraries:
            for lib_name, lib_address in libraries.items():
                if not lib_address:
                    raise Exception(f"Missing contract address for library {lib_name}. Cannot continue")
                linkRef_positions = compiled_sol["contracts"]["smart_contract.sol"][contract_name]["evm"]["bytecode"]["linkReferences"]["smart_contract.sol"][lib_name]
                if lib_name not in compiled_sol["contracts"]["smart_contract.sol"]:
                    raise ValueError(f"Libray name not found in compiled code: {lib_name}")
                #lib_bytecode = compiled_sol["contracts"]["smart_contract.sol"][lib_name]["evm"]["bytecode"]["object"]
                for pos in linkRef_positions:
                    #breakpoint()
                    start = pos["start"] * 2
                    length = pos["length"] * 2
                    bytecode = bytecode[:start] + lib_address[2:] + bytecode[start+length:] # lib_address[2:] -> omit the initial 0x...


        assert re.fullmatch(r"^[0-9a-fA-F]+$", bytecode) # only hex chars allowed in bytecode

        return bytecode

    @property
    def compiled_sol(self):
        return self._compiled_sol

    def compile(self, prefix:str="smart_contract", debug:bool=False):

        debug = True
        try:
            solcx.set_solc_version(settings.SOLC_VERSION) #"0.8.0")
        except solcx.exceptions.SolcNotInstalled:
            print(f"Installing solc v{settings.SOLC_VERSION} ...")
            solcx.install_solc(settings.SOLC_VERSION) #"0.8.0")
            solcx.set_solc_version(settings.SOLC_VERSION) #"0.8.0")

        print(f"Using solc v{settings.SOLC_VERSION} ...")

        imports_text = "\n".join(map(lambda i: f"import '{i}';", self._imports))
        #breakpoint()
        libraries_text = "\n".join(map(lambda l: l.compile() + "\n", self.libraries.values()))
        functions_text = "\n".join(map(lambda f: f.compile() + "\n", self.functions)) 
        attributes_text = "\n".join(map(lambda c: c.compile() + "\n", self.attributes)) 
        contracts_text = "\n".join(map(lambda c: c.compile() + "\n", self.contracts.values())) 
        #breakpoint()
        types_text = "\n".join(map(lambda i: f"type {i[0]} is {i[1]};", self._types.items()))
        enums_text = "\n".join(map(lambda c: c.compile()+"\n", self.enumerations))    
        structs_text = "\n".join(map(lambda c: c.compile()+"\n", self.structures))    


        verbatim = self._verbatim       
        smart_contract_text = f"""
// SPDX-Licence-Identiier: CC-BY-NC-4.0	

pragma solidity >= {self._version};
pragma abicoder v2;

{verbatim}

{imports_text}

{types_text}

{enums_text}

{structs_text}

{attributes_text}

{functions_text}

{libraries_text}

{contracts_text}
"""

        #breakpoint()
        if (debug):
            file_name = "_".join([prefix,datetime.datetime.now().strftime("%y%m%d_%H%M%S")])
            #tmp_path = f"{settings.BASE_DIR}\..\public\\tmp\{file_name}.sol"
            tmp_path = os.path.join(settings.BASE_DIR, "..", "public", "tmp", f"{file_name}.sol")
            with open(tmp_path,"w") as file:
                file.write(smart_contract_text)
                print("\nSmart contract saved at: ",tmp_path,"\n")

        try:

            solc_configuration = {
                    "language": "Solidity",
                    "sources": 
                        {
                            f"smart_contract.sol": 
                                {
                                    "content": smart_contract_text
                                }
                        },
                    "settings": {
                        "optimizer": {
                            "enabled": True,
                            "runs": 40000        # or 10000–50000 depending on your needs
                        },
                        "outputSelection": {
                            "*": {"*": ["abi", "metadata", "evm.bytecode", "evm.sourceMap"]}
                        },
                        #"libraries": {"strings.sol"}
                    },
                }

            self._compiled_sol = solcx.compile_standard(
                solc_configuration,
                # TODO add a setting parameter for solc version
                solc_version = settings.SOLC_VERSION, #"0.8.0",
                allow_paths = ["."]
            )

        except Exception as err:
            print(f"Errors compiling smart-contract code: {err}")    
            self._compiled_sol = None


        

        
