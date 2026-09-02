#from distutils.log import debug
from django.utils import timezone
from django.db import transaction
from django.db.models import Q
import glob
import json
from tracemalloc import start
from nfa import NFA, LTS, InputScanner
import traceback
import sys
import os
import re
from generator import SmartContractGenerator, MPSTSmartContractGenerator
import time
from tabulate import tabulate
from django.conf import settings
import statistics
from datetime import datetime
import uuid
from django.core.files import File
from pathlib import Path
import prompt_toolkit
from prompt_toolkit.history import FileHistory
from prompt_toolkit.completion import NestedCompleter
from web3 import Web3
from engine.models import ActionFilter, UnionFilter, Filter, Contract, Configuration, RunningInstance, Engine, EngineOnChain, EngineOffChain

import random
import string
import subprocess
import pyperclip
from django.contrib.sites.models import Site

def random_string(length):
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))


class Enforcer:

    def __init__(self, engine : Engine):
#        assert nfa is not None, f"Expected not-null nfa to build an enforcer"
        self._debug : bool = True
        self._onChain : bool = isinstance(engine, EngineOnChain)
        
        #self._history = []  
        self._engine = engine

        #self._append_history("",self._engine.get_curr_states(), self._engine.get_buffer_items())   

    def __str__(self):
        return f"Engine: {self._engine}, Debug: {self._debug}"

    @property
    def engine(self):
        return self._engine

    def set_engine(self, new_engine):
        if self._engine != new_engine:
            print(f"WARNING: replacing old engine ({self._engine}) with new one ({new_engine}).")
            self._engine = new_engine
 
    @property
    def buffer(self):
        return self._engine.get_buffer_items() if self._engine else None
 
    @property
    def kb(self):
        return self._engine.get_kb() if self._engine else None
  
    @property
    def history(self):
        #return self._history
        return self._engine.history if self._engine else None

    # DEBUG LOG

    def set_debug(self, debug: bool):
        self._debug = debug


    def _debug_log(self, text):
        if self._debug:
            print(text)

#    def _append_history(self, event : str, curr_states : list, buffer : list):
#        self.history.append({
#            "event" : event, 
#            "curr_states" : curr_states, 
#            "buffer" : buffer}
#        )

    def ended(self):
        return self._engine.ended()


    def _parse_event(self, text):
        #m = re.match(r"^(([a-zA-Z0-9&|!\(\)]+):)?([a-zA-Z0-9_]+)([?!])([a-zA-Z0-9_]+)(\(([a-zA-Z0-9_,]+)\))?$", text)
        #breakpoint()
        #m = re.match(r"^(([a-zA-Z0-9&|!\(\)]+):)?([a-zA-Z0-9_]+[?!][a-zA-Z0-9_]+)(\(([a-zA-Z0-9_,]+)\))?$", text)
        m = re.match(r"^(([a-zA-Z0-9&|!\(\)]+):)?([^!?]+[?!][^!?]+)(\(([a-zA-Z0-9_,]+)\))?$", text)

        #breakpoint()
        if not m:
            #breakpoint()
            raise Exception(f"Event has an unrecognized format: {text}")

        #breakpoint()
        #_, precondition, actor, action, message, _, knowledge = m.groups()
        _, precondition, event, _, knowledge = m.groups()

        if knowledge:
            knowledge = knowledge.strip("()").split(",")

        #return precondition, actor, action, message, knowledge
        return precondition, event, knowledge


    # PROCESSORS
    def process_input(self, symbol): #event_stream : str):

        #precondition, actor, action, message, knowledge = self._parse_event(event)
        #breakpoint()
        precondition, event, knowledge = self._parse_event(symbol)

        #num_states_pre = self._engine.get_num_states() #en(self._curr_states)

        #out = self._engine.process_input(event)
        out = self._engine.process_input(precondition, event, knowledge)
        #nd_factor = (self._engine.get_num_states() - num_states_pre) / num_states_pre
        
        #self._debug_log(f"(* Non-determinism factor: {nd_factor} *)")
        
        return out

    def process_check(self):
        out = None
        try:
            out = self._engine.process_check()

        except Exception:
            traceback.print_exc()
            pass

        return out

    class NoMessageFound(Exception):
        pass

from enforcer import *
from bpmn_parser.models import *
from mpst.models import MPST

# TODO merge this model with the UI env (a regular dictionary)
class Model:

    def __init__(self):
        self._store = {}

    def set_object(self, name, obj):
        self._store[name] = obj
    
    def get_object(self, name):
        return self._store.get(name, None)

    def unset_object(self, name):
        if name in self._store:
            del self._store[name]

    @property
    def names(self):
        return self._store.keys()


class UICommand:

    class Error(Exception):
        pass
    
    _description = ""

    def __init__(self, ui):
        assert isinstance(ui, UI)
        self._ui = ui

    @property
    def description(self):
        return self._description or ""

    @property
    def ui(self):
        return self._ui

    def get_completions(self):
        return None

    def execute(self, *args, **kwargs):
        raise Exception("You must implement this")


class CmdInit(UICommand):

    def execute(self, *args, **kwargs):
##
##        choreographies = [
##            ("diagram", "diagram.bpmn", ),
##            ("diagram_minimal", "diagram_minimal.bpmn"),
##            ("diagram_basic", "diagram_basic.bpmn"),
##            ("diagram_gateways", "diagram_gateways.bpmn", ),
##            ("diagram_gateways_mismatch", "diagram_gateways_mismatch.bpmn", ),
##            ("diagram_gateways_dangling", "diagram_gateways_dangling.bpmn", ),
##            ("diagram_gateways_nested", "diagram_gateways_nested.bpmn", ),
##            ("diagram_gateways_nested_intermediate", "diagram_gateways_nested_with_intermediate_task.bpmn", ),
##            ("diagram_gateways_nested_inclusive", "diagram_gateways_nested_inclusive.bpmn", ),
##            ("diagram_gateways_nested_dangling", "diagram_gateways_nested_dangling.bpmn", ),
##            ("diagram_construction_industry", "diagram_construction_industry.bpmn"),
##            ("diagram_patient_doctor","diagram_patient_doctor.bpmn"),
##            ("diagram_incident_management", "diagram_incident_management.bpmn")
## 
##        ]
##
        #for name, filename in choreographies:
        for filename in os.listdir(os.path.join(settings.DATA_ROOT, "BPMN")):
            name = filename.split(".")[0] # remove the final dot extension
            filepath = Path(settings.DATA_ROOT, "BPMN", filename)
            #breakpoint()
            attribs = {
                "name": name,
                #"resource": os.path.join("BPMN", filename), #os.path.join(settings.MEDIA_ROOT, filename),
                "resource": File(filepath.open("rb"), name=filename)
            }
            
            c, created = Choreography.objects.get_or_create(name=name, defaults=attribs)
            if created:
                print(f"Choreography {name} imported ...")
            else:
                print(f"Choreography {name} already exists ...")

        for filename in os.listdir(os.path.join(settings.DATA_ROOT, "MPST")):
            name = filename.split(".")[0] # remove the final dot extension
            filepath = Path(settings.DATA_ROOT, "MPST", filename)
            #breakpoint()
            attribs = {
                "name": name,
                #"resource": os.path.join("BPMN", filename), #os.path.join(settings.MEDIA_ROOT, filename),
                "resource": File(filepath.open("rb"), name=filename)
            }
            
            c, created = MPST.objects.get_or_create(name=name, defaults=attribs)
            if created:
                print(f"MPST {name} imported ...")
            else:
                print(f"MPST {name} already exists ...")
        
    

class CmdSetFilter(UICommand):

    _description = "Set a filter"


    def execute(self, *args, **kwargs):
        if len(args) < 1:
            raise Exception(f"Missing argument: None | <filter_expression>")

        exp = args[0].strip()
        if exp == "None":
            self.ui.set_env("filter", Filter())
        else:
            try:
                #breakpoint()
                exp_list = exp.split("|")
                filters_list = []   
                for exp in exp_list:
                    exp = exp.strip()
                    if exp[0] == "<" and exp[-1] == ">":
                        parts = exp[1:-1].split(",")
                        source = parts[0].strip()
                        action = parts[1].strip()
                        message = parts[2].strip()
                        
                        filters_list.append(ActionFilter(source, action, message))
                
                num_filters = len(filters_list)
                if num_filters == 0:
                    raise Exception(f"Ill-formed list filter expression: {exp_list}")
                elif num_filters == 1:
                    self.ui.set_env("filter", filters_list[0])
                elif num_filters > 0:
                    self.ui.set_env("filter", UnionFilter(*filters_list))
                
            except Exception:
                raise Exception(f"Ill-formed filter expression: {exp}")

class CmdStep(UICommand):

    _description = "Execute a given number of steps of the already loaded script"

    def execute(self, *args, **kwargs):

        steps = int(args[0]) if len(args) > 0 else None

        if steps and int(steps) <= 0:
            raise Exception("You must specify a positive number")

        self.execute_steps(steps)

    def execute_steps(self, num_steps):
        # num_steps == None : execute all the steps of the script

        #breakpoint()
        if num_steps is not None and num_steps <= 0:
            raise Exception(f"Expected at least one step to execute. Pass: {num_steps}")

        ri = self.ui._model.get_object("ri")

        if not ri:
            raise Exception("This command is applicable only after starting a running instance")            

        the_script = self.ui._model.get_object("script")

        script_position = self.ui._model.get_object("script_position")

        if not the_script or script_position is None:
            raise Exception("This command is applicable only after loading a script")            

        if script_position < 0:
            raise Exception(f"The position should always be zero or positive. Read: {script_position}")

        script_len = len(the_script)

        while script_position < script_len and (num_steps is None or num_steps > 0):

            line = the_script[script_position].strip()
            if line[0] == "#":
                # this is a comment
                continue
            try: 
                ri.append_input(line)            
                out = ri.enforcer.process_input(line)
                if out:
                    ri.append_output(out)
                script_position = script_position + 1
                num_steps = num_steps - 1 if num_steps is not None else None
                self.ui._model.set_object("script_position", script_position)

            except Exception as err:
                print(f"Error executing script: {err}")
                traceback.print_exc()
                return
 
class CmdReplay(UICommand):

    _description = "Save the sequence of input events on the running instance on a script file"

    def execute(self, *args, **kwargs):

        path = args[0] if len(args) > 0 else None
        if not path:
            raise Exception("Script not passed")

        if os.path.exists(path):
            raise Exception("Path already exists: {path}. Cannot overwrite at the moment")

        with open(path, "w+") as the_script:
            for line in self.ui.ri.input_events:
                the_script.write(line + "\n")

        print(f"Script file saved at position: {path}")


class CmdScript(CmdStep):

    _description = "Load a script from file (require a running instance already loaded)"

    def execute(self, *args, **kwargs):

        path = args[0] if len(args) > 0 else None

        steps = int(args[1]) if len(args) > 1 else None

        if not path:
            raise Exception("Script not passed")

        if not os.path.exists(path):
            raise Exception(f"Script path does not exist")
        elif os.path.isdir(path):
            #breakpoint()
            files = sorted(
                (p for p in Path(path).iterdir() if p.is_file()),
                key=lambda p: p.name.lower()
            )
            for f in files:
                print(f"* {f.name}")           
        elif os.path.isfile(path):
    
            with open(path, "r") as the_script:
    
                lines = the_script.readlines()
                self.ui._model.set_object("script", lines)
                self.ui._model.set_object("script_position", 0)
    
            self.execute_steps(steps)
        else:
            raise Exception(f"Condition not handled")
      

class CmdDebug(UICommand):

    _description = "Activate/deactivate debug mode"

    def get_completions(self):

        return { "on" : None, "off": None }

    def execute(self, *args, **kwargs):

        status = "on"
        if len(args) > 0:
            status = args[0]

        if status not in [ "on", "off" ]:
            raise Exception(f"Status not recognized: {status}")

        print(f"Set debug mode : {status}")

        self.ui._debug = (status == "on")
        if self.ui._enforcer:
            self.ui._enforcer.set_debug(self.ui._debug)



class CmdQuit(UICommand):

    _description = "Exit the command line interpreter"

    def execute(self, *args, **kwargs):
        raise KeyboardInterrupt()


class CmdHelp(UICommand):
    
    _description = "Print this help page"

    def execute(self, *args, **kwargs):
        print("Available commands: ")

        max_len = max(map(lambda name: len(name), self.ui._registry.keys()))

        for name, cmd in sorted(self.ui._registry.items()):
            label = name.ljust(max_len + 2, ".")
            print(f"/{label} : {cmd.description}")
        #print(", ".join(sorted(self.ui._registry.keys())))


class CmdListInstances(UICommand):

    _description = "List all the running instances loaded in the database"

    def execute(self, *args, **kwargs):

        print("Running instances:")
        instances = RunningInstance.objects.all()
        if len(instances) == 0:
            print("(* none *)")
        else:
            for ri in RunningInstance.objects.all():
                print(f" * {ri.id} : {ri}")

class CmdListChoreographies(UICommand):

    _description = "List all choreographies loaded in the database"

    def execute(self, *args, **kwargs):

        print("Available choreographies: (type / # states / # transitions / # messages)")
        items_bpmn = Choreography.objects.all().order_by("name")
        items_mpst = MPST.objects.all() #.order_by("name")

        items = sorted(list(items_bpmn.all()) + list(items_mpst.all()), key=lambda c: c.name)

        #breakpoint()
        if len(items) == 0:
            print(f"(* none *)")
        else:
            longest = 0
            for c in items:
                if len(c.name) > longest:
                    longest = len(c.name)

            for c in items:
                #breakpoint()
                curr_type = "BPMN" if c.__class__ == Choreography else "MPST"
                cho_name = c.name.ljust(longest+3,".")
                details = ""
                try:
                    if not c.enabled:
                        details = f"{curr_type:4} (not enabled)"
                    elif curr_type == "BPMN":
                        nfa = c.to_nfa(optimize=True)
                        nfa_optimized = c.to_nfa(optimize=True,silent=True)
                        no_states = len(nfa.states)
                        no_transitions = len(nfa.transitions)
                        no_messages = len(nfa.messages)
                        #no_states_o = len(nfa_optimized.states)
                        #no_transitions_o = len(nfa_optimized.transitions)
    
                        details = f"{curr_type:4} ({no_states:>3}/{no_transitions:>3}/{no_messages:>3})" 
                    elif curr_type == "MPST":
                        no_states = len(c.root.state_vars)
                        no_transitions = len(c.root.transforms)

                        no_messages = len(c.root.events) #"?" #len(nfa.messages)


                        details = f"{curr_type:4} ({no_states:>3}/{no_transitions:>3}/{no_messages:>3})" 
                    else:
                        details = f"{curr_type:4} (Not handled)" 
                except Exception as err:
                    no_states = "NN"
                    no_transitions = "NN"
                    no_messages = "NN"
                    details = f"{curr_type:4} (Error: {str(err)})"
                    c.details = traceback.format_exc()
                    c.save()
                    #traceback.print_exc()

                finally:
                    resource_name = str(c.resource)
                    if len(resource_name) < 53:
                        resource_name = resource_name[:50]

                    resource_name = resource_name.ljust(53, ".")
                    print(f"* {cho_name} - {resource_name:>23} - {details}")


class CmdClear(UICommand):

    _description = "Remove all choreographies"

    def execute(self, *args, **kwargs):

        num_cho = Choreography.objects.all().count()
        while True:
            confirm = self.ui.prompt(f"Do you want to remove {num_cho} choreography/ies? [(y)es/(N)o/(l)ist]")
            if confirm.lower() == "y":

                Choreography.objects.all().delete()
                break
            elif confirm.lower() == "l":
                print("Available choreographies:")
                items = Choreography.objects.all()
        
                if len(items) == 0:
                    print(f"(* none *)")
                else:
                    longest = 0
                    for c in items:
                        if len(c.name) > longest:
                            longest = len(c.name)
        
                    for c in items:
                        cho_name = c.name.ljust(longest+3,".")
                        print(f"* {cho_name} - {c.resource}")

            else:
                print(f"Operation interrupted by the user")
                break


class CmdRemove(UICommand):

    _description = "Remove the choreography with the given name"
    
    def get_completions(self):

        d = {}
        for c in Choreography.objects.all():
            d[c.name] = None
        return d

    def execute(self, name, *args, **kwargs):

        c = Choreography.objects.filter(name=name).first()
        if c is None:
            print(f"Choreogrpahy '{name} does not exist")
        else:
            confirm = self.ui.prompt(f"Do you want to remove choreography {c.name} ({c.resource}) from the enforcer database? [y/N]")
            if confirm.lower() == "y":
                c.delete()
            else:
                print(f"Operation interrupted by the user")

class CmdLoadConfiguration(UICommand):

    _description = "Load an existing blockchain configuration from database"

    def get_completions(self):

        #breakpoint()
        d = {}
        for c in Configuration.objects.all():
            d[c.label] = None

        return d

    def execute(self, label=None, *args, **kwargs):
        #breakpoint()
        #label = args[0] if len(args) > 0 else None

        if not label:
            print(f"Please, specify the label of the configuration to load. Available configurations:")
            config_labels = list(map(lambda c: f"* {c.label}", Configuration.objects.all()))
            if len(config_labels) > 0:
                available = "\n".join(config_labels)
            else:
                available = "(* none *)"
            print(available)
            return

        c_list = Configuration.objects.filter(label__icontains=label)

        if len(c_list) > 0:
            c = c_list[0]
            #self.ui._model.add_object("", c)
            self.ui.set_env("ONCHAIN_URL", c.url)
            self.ui.set_env("ONCHAIN_CHAIN_ID", c.chain_id)
            self.ui.set_env("ONCHAIN_ADDRESS", c.address)
            self.ui.set_env("ONCHAIN_PRIVATE_KEY", c.private_key)
            print(f"Configuration loaded: {c.label}. Checkout the new /env")
    
        else:    

            print(f"Configuration containing label (*{label}*) does not exist")

class CmdGetBalance(UICommand):

    _description = "Return the balance of the wallet address currently configured in the environment"

    def get_completions(self):

        #breakpoint()
        d = {}
        for c in Configuration.objects.all():
            d[c.label] = None

        return d


    def execute(self, label=None, *args, **kwargs):
 
        chain_url = self.ui.get_env("ONCHAIN_URL")
        address = self.ui.get_env("ONCHAIN_ADDRESS")

        if label:
            c_list = Configuration.objects.filter(label__icontains=label)
            if len(c_list) == 0:
                print(f"Cannot find configuration matching label: {label}")
            else:
                chain_url = c_list[0].url
                address = c_list[0].address
    
        if not chain_url:
            print(f"Cannot find a blockchain URL in the env or in the passed configuration")
        elif not address:
            print(f"Cannot find wallet address in the env or in the passed configuration")
        else:        

            try:
                w3 : Web3 = Web3(Web3.HTTPProvider(chain_url, request_kwargs={"timeout": 300}))
                balance = w3.eth.get_balance(address)
                balance_eth = w3.from_wei(balance, 'ether')

                print(f"Account: {address}. Balance: {balance_eth} ETH")
            except Exception as err:
                print(f"Error fetching balance. Account: {address}. URL: {chain_url}")
    

class CmdOpenFile(UICommand):

    _description = "Opens a file or a choreography in the local system given its path or name"

    def execute(self, path=None, extra=None, *args, **kwargs):

        if not path:
            c : Choreography = self.ui._model.get_object("choreography")
            m : MPST = self.ui._model.get_object("mpst")

            if c:
                path = c.name
            elif m:
                path = m.resource.path
            else:
                print("Please, specify a resource you want to open, i.e. either: 1) a file path, or 2) a choreography name, or 3) a MPST name.")
                return

        if not os.path.exists(path):
    
            found = Choreography.objects.filter(Q(resource=path)|Q(name=path))
            if len(found) > 0:
                try:
                    found = found[0]
                    site = Site.objects.first()
                    path = f"http://{site.domain}#{found.name}"
            
                except Exception as err:
                    print(f"Cannot detect choen frontend: {err}")
                    return
            else:
                print(f"File or choreography does not exist: {path}")
                return

        try:
            if extra == "copy":
                with open(path, "r") as f:
                    content = f.read()
                    pyperclip.copy(content)
                    print(f"Content copied on clipboard from file: {path} ...")

            else:
                subprocess.run(["open", path])
                print(f"Opening file with system shell: {path} ...")
        except Exception as err:
            print(f"Error opening file: {path}. Details: {err}")

class CmdBuildContracts(UICommand):

    _description = "Compile smart contracts from the current choreography"
    
    def execute(self, name=None, *args, **kwargs):

        c : Choreography = self.ui._model.get_object("choreography")
        m : MPST = self.ui._model.get_object("mpst")
        debug = True

        if c and m:
            print(f"Both choreography ({c}) and MPST ({m}) are loaded")
            return

        if c:
            #nfa.remove_epsilon_transitions()
            #nfa.remove_unreachable_states()

            
            nfa : NFA = self.ui._model.get_object("nfa")
            if not nfa:
                print("Unexpected error when loading current choreography: no NFA generated")
                return

            #self.compile(nfa)

            #breakpoint()
            self.compile_nfa(nfa, debug=debug)
        elif m:
            #scg = MPSTSmartContractGenerator(m.root)
            #c = scg.createSmartContract()
            #c.compile(debug=True)
            self.compile_mpst(m, debug=debug)
        else:
            print("No choreography and no MPST loaded, yet. Cannot continue")
            return


    
    def compile_nfa(self, nfa, debug=False):

        #nfa = c.to_nfa(optimize=True)
        #breakpoint()
        scg: SmartContractGenerator = SmartContractGenerator(nfa)

        compiled_sol = scg.createSmartContract().compile(debug=debug)

    def compile_mpst(self, m : MPST, debug=False): 
        scg = MPSTSmartContractGenerator(m.root)
        c = scg.createSmartContract()
        c.compile(debug=debug)

 
class CmdLoadMPST(UICommand):

    _description = "Load a Multi-Party Session Type from database"

    def execute(self, name=None, *args, **kwargs):

        if not name:
            print("Please, specify a MPST to load. Available MPSTs:")
            available = "\n".join(map(lambda c: f"* {c.name}", MPST.objects.all()))
            print(available)
            return

        try:
            c : MPST = MPST.objects.get(name=name)
            self.ui._model.set_object("mpst", c)
            self.ui._model.set_object("lts", c.root)
            print(f"MPST '{name}' loaded ...")
        except Exception as e: # MPST.DoesNotExist as e:
            #breakpoint()
            if os.path.exists(name):
                if os.path.isfile(name):
                    self.import_file(name)
                else:
                    # recursively scan directory
                    for filename in glob.iglob(name + '/**/*.mpst', recursive=True):
                        self.import_file(filename)

            else:
                print(f"Cannot find MPST {name}")

    def import_file(self, name):
        #breakpoint()
        mpst_name = os.path.basename(name).rsplit(".",1)[0]
        attribs = {
            "name": mpst_name,
            "resource": File(open(name)),
        }
        c, created = MPST.objects.get_or_create(name=mpst_name, defaults=attribs)

##        try:
##            c.to_nfa()
##        except Exception as err:
##            traceback.print_exc()
##            print(f"KO MPST {mpst_name} : error extracting NFA ({err}), cannot import ...")
##            return

        self.ui._model.set_object("mpst", c)
        if created:
            print(f"OK MPST {mpst_name} : imported and loaded ...")
        else:
            print(f"OK MPST {mpst_name} : already exists and has been loaded ...")
 

class CmdLoadChoreography(UICommand):

    _description = "Load a choreography from database"

    def get_completions(self):
 
        d = {}
        for c in Choreography.objects.all():
            d[str(c.name)] = None

        #breakpoint()
        return d
   
    def execute(self, name=None, *args, **kwargs):

        if not name:
            print("Please, specify a choreography to load. Available choreographies:")
            available = "\n".join(map(lambda c: f"* {c.name}", Choreography.objects.all()))
            print(available)
            return

        try:
            c : Choreography = Choreography.objects.get(name=name)
            self.ui._model.set_object("choreography", c)

            rei : REI = c.to_rei()
            self.ui._model.set_object("rei", rei)

            nfa : NFA = c.to_nfa(optimize=True)
            #self.ui._model.set_object("nfa", nfa)
            self.ui._model.set_object("lts", nfa)

            
            

            print(f"Choreography '{name}' loaded ...")
        except Choreography.DoesNotExist as e:
            #breakpoint()
            if os.path.exists(name):
                if os.path.isfile(name):
                    self.import_file(name)
                else:
                    # recursively scan directory
                    for filename in glob.iglob(name + '/**/*.bpmn', recursive=True):
                        self.import_file(filename)

            else:
                print(f"Cannot find choreography {name}")

    def import_file(self, name):
        #breakpoint()
        cho_name = os.path.basename(name).rsplit(".",1)[0]
        attribs = {
            "name": cho_name,
            "resource": File(open(name)),
        }
        c, created = Choreography.objects.get_or_create(name=cho_name, defaults=attribs)

        try:
            c.to_nfa(optimize=True)
        except Exception as err:
            traceback.print_exc()
            print(f"KO Choreography {cho_name} : error extracting NFA ({err}), cannot import ...")
            return

        self.ui._model.set_object("choreography", c)
        if created:
            print(f"OK Choreography {cho_name} : imported and loaded ...")
        else:
            print(f"OK Choreography {cho_name} : already exists and has been loaded ...")
 
 

class CmdStop(UICommand):

    _description = "Stop the running instance that is executing right now"
    
    def execute(self, *args, **kwargs):

        ri : RunningInstance = self.ui._model.get_object("ri")

        if not ri:
            raise Exception("No running instance to stop")

        ri.stop()
        self.ui._model.set_object("ri", None)
 
class CmdPause(UICommand):
  
    _description = "Exit from the run-time prompt, without stopping the running instance"

    def execute(self, *args, **kwargs):

        ri : RunningInstance = self.ui._model.get_object("ri")

        if not ri:
            raise Exception("No running instance to pause")

        self.ui._model.set_object("ri", None)

class CmdStart(UICommand):

    _description = "Create a running instance from the currently loaded choreography"


    @transaction.atomic
    def execute(self, *args, **kwargs): #contract_address=None, *args, **kwargs):

        #breakpoint()
        cho : Choreography = self.ui._model.get_object("choreography")
        mpst : MPST = self.ui._model.get_object("mpst")

        #if len(args) > 0:
        #    cho = Choreography.objects.get(name=args[0])

        if not cho and not mpst:
            raise UICommand.Error("You must load a choreography or a MPST or start a choreography")

    
        #breakpoint()

        # 0. create a stub of running instance
        ri = RunningInstance()
        if cho:
            ri.choreography = cho
        elif mpst:
            ri.mpst = mpst
        else:
            raise UICommand.Error("You must pass either a MPST or a Choreography")
            
        ri.label = cho.name if cho else mpst.name

        ri.save()

        onchain_url = self.ui.get_env("ONCHAIN_URL")
        onchain_chain_id = int(self.ui.get_env("ONCHAIN_CHAIN_ID", 0))
        onchain_address = self.ui.get_env("ONCHAIN_ADDRESS")
        onchain_private_key = self.ui.get_env("ONCHAIN_PRIVATE_KEY")
 

        #breakpoint()

        log_file = self.ui.get_env("LOG_FILE", None)
        filter = self.ui.get_env("FILTER", None)

        if onchain_url and onchain_chain_id and onchain_address and onchain_private_key:

            conf_list = Configuration.objects.filter(url=onchain_url, chain_id=onchain_chain_id, address=onchain_address, private_key=onchain_private_key)
    
            if len(conf_list) > 0:
                conf = conf_list[0]
            else:

                suffix = datetime.now().strftime("%Y%m%d_%H%M%S")

                conf = Configuration()
                conf.url = onchain_url
                conf.chain_id = onchain_chain_id
                conf.address = onchain_address
                conf.private_key = onchain_private_key
                conf.label = f"New configuration {suffix}"
                conf.save()


            engine = ri.setup_onchain(conf, log_file=log_file, filter=filter)

        else:

            engine = ri.setup_offchain(log_file=log_file, filter=filter)

        assert engine is not None
        enforcer = Enforcer(engine)
        ri.set_enforcer(enforcer)

        if not ri.running:
            ri.running = True
            ri.save()

        self.ui._model.set_object("ri", ri)


class CmdLogOnOff(UICommand):

    _description = "Activate/deactivate writing operations on log file"

    def execute(self, on_off=None, log_file=None, *args, **kwargs):
        if on_off is None:
            print(f"LOG_FILE: {self.ui.get_env('LOG_FILE', '')}")
        elif on_off == "on":
            self.ui.set_env("LOG_FILE", log_file or "choen.log")
        elif on_off == "off":
            self.ui.set_env("LOG_FILE", None)
        else:
            print(f"Value not recognized: {on_off}")


class CmdLoadInstance(UICommand):

    _description = "Load a running instance previously paused and prepare to intereact with it throug the command line"

    def get_completions(self):
        d = {}

        for ri in RunningInstance.objects.all():
            d[str(ri.id)] = None

        return d

    def execute(self, ri_id=None, *args, **kwargs):

        #breakpoint()

        if not ri_id:
            print(f"Please, specify a running instance to load. Available instances:")
            instances = RunningInstance.objects.all()
            if len(instances) > 0:
                for ri in instances:
                    print(f" * {ri.id} : {ri}")
            else:
                print("(* none *)")

        else:
    
            try:
                # 1. load instance
                ri : RunningInstance = RunningInstance.objects.get(id=ri_id)

                #breakpoint()
                #automaton = ri.choreography.to_nfa()

                # 2. load the environment from the running instance blockchain configuration
                if ri.blockchain_configuration:

                    sc_enforcer = ri.engineonchain.contract_enforcer #Contract.objects.filter(running_instance=ri, label="enforcer").first()
                    if not sc_enforcer:
                        raise Exception(f"Cannot find smart contract address for running instance: {ri}")
                    contract_address = sc_enforcer.contract_address

                    self.ui.set_env("ONCHAIN_URL", ri.blockchain_configuration.url)
                    self.ui.set_env("ONCHAIN_CHAIN_ID", ri.blockchain_configuration.chain_id)
                    self.ui.set_env("ONCHAIN_ADDRESS", ri.blockchain_configuration.address)
                    self.ui.set_env("ONCHAIN_PRIVATE_KEY", ri.blockchain_configuration.private_key)



                    log_file = self.ui.get_env("LOG_FILE", None)
                    engine = ri.setup_onchain(ri.blockchain_configuration, log_file=log_file)

##                    self.setup_onchain_running_instance(ri, contract_address) # automaton, contract_address, ri.blockchain_configuration)
##
                else:
                    self.ui.set_env("ONCHAIN_URL", None)
                    self.ui.set_env("ONCHAIN_CHAIN_ID", None)
                    self.ui.set_env("ONCHAIN_ADDRESS", None)
                    self.ui.set_env("ONCHAIN_PRIVATE_KEY", None)


                    log_file = self.ui.get_env("LOG_FILE", None)
                    engine = ri.setup_offchain(log_file=log_file)
##                    self.setup_offchain_running_instance(ri) #, automaton)
##
##
##                # 3. call the setup_onchain/offchain_engine
##
##                # 4. set the running instance
                self.ui._model.set_object("ri", ri)
                if ri.choreography:
                    self.ui._model.set_object("choreography", ri.choreography)

                    nfa : NFA = ri.choreography.to_nfa(optimize=True)
                    #self.ui._model.set_object("nfa", nfa)
                    self.ui._model.set_object("lts", nfa)
                    engine.set_nfa(nfa)
                elif ri.mpst:
                    self.ui._model.set_object("mpst", ri.mpst)
                    self.ui._model.set_object("lts", ri.mpst.root)
                        
                assert engine is not None
                enforcer = Enforcer(engine)
                ri.set_enforcer(enforcer)




            except RunningInstance.DoesNotExist as e:
                print(f"Cannot find running instance {ri_id}")
                 

class CmdSmooth(UICommand):
    
    _description = "Generate a random walk that smoothly reaches a final state"

    def execute(self, *args, **kwargs):
 
        nfa = self.ui._model.get_object("nfa")
        if not nfa:
            raise UICommand.Error("Cannot continue without a loaded NFA")

        ri = self.ui._model.get_object("ri")

        if not ri:
            raise UICommand.Error("Cannot continue without a running instance")

        source = None
        targets = None

        if len(args) > 0:
            if args[0] == "~>":
                targets = args[1:]
            else:
                source = args[0]    
                if len(args) > 1:
                    if args[1] != "~>":
                        raise UICommand.Error("Wrong syntax: expected '/smooth' or '/smooth [source] ~> [target1] ... [targetN]'")
                    if len(args) > 2:
                        targets = args[2:]

       
        #breakpoint()
        paths = nfa.smooth_paths(source=source, targets=targets)
        
        if len(paths) == 0:
            raise UICommand.Error(f"No smooth path available from initial state to target states: {targets or 'Final states'}")

        chosen_path = list(random.choice(paths))

        print("===")
        print(f"Chosen path ({len(chosen_path)}) :")
        for transition in chosen_path:
            print(transition)
        print("===")

        #breakpoint()
        for transition in chosen_path:
    
            ri.append_input(transition.label)
            out = ri.enforcer.process_input(transition.label)
            if out:
                ri.append_output(out)
    
            out = ri.enforcer.process_check()
            if out:
                ri.append_output(out)
    
        

class CmdRandom(UICommand):

    _description = "Generate random input and pass it to the currently loaded running instance"

    def execute(self, *args, **kwargs):

        nfa = self.ui._model.get_object("nfa")
        if not nfa:
            raise UICommand.Error("Cannot continue without a loaded NFA")

        ri = self.ui._model.get_object("ri")

        if not ri:
            raise UICommand.Error("Cannot continue without a running instance")

        end = args[0].strip() if len(args) > 0 else "1"

        if end == "end":
            while not nfa.is_final(ri.engine.get_curr_states()):
                self._emit_random_event(nfa, ri)
        elif end.isdigit():

            for i in range(int(end)):
                self._emit_random_event(nfa, ri)
        else:
            raise UICommand.Error(f"Ill-formed argument: {args[0]}. Expected: end | <positive_integer>")
    
    def _emit_random_event(self, nfa : NFA, ri : RunningInstance):

        #breakpoint()
        coin = random.randint(0, 100)
        if coin < 5:

            # 5% of the times, generate a completely random event

            actor = random.choice(list(nfa.agents))  #random_string(10)
            msg = random.choice(list(nfa.messages)) #random_string(10)
            action = random.choice(["?","!"])
            random_event = f"{actor}{action}{msg}"

        elif coin < 55:
        
            # 50% of the times, generate a random event among those accepted in the current states
            enabled_transitions = nfa.enabled_transitions(ri.engine.get_curr_states()) #ri.engine.curr_states)

            random_event = random.choice(enabled_transitions).label

        else:

            # 45% of the times, pick an actual event of the nfa

            random_event = random.choice(list(nfa.events))
    
        ri.append_input(random_event)
        out = ri.enforcer.process_input(random_event)
        if out:
            ri.append_output(out)

        out = ri.enforcer.process_check()
        if out:
            ri.append_output(out)


class CmdDump(UICommand):

    _description = "Print information of the currently loaded configuration or the currently running instance"

    def get_completions(self):
        d = {
            "curr_states": None,
            "transitions": None,
            "states": None,
            "rei": None,
            "nfa": None,
            "buffer": None,
            "instance": None,
            "input": None,
            "output": None,
        }

        return d

    def execute(self, *args, **kwargs):

        #breakpoint()

        if len(args) == 0:
            print("Please specify an argument: dump <" + "|".join(self.get_completions().keys()) + ">") #curr_states|states|transitions|buffer|rei>")
        else:
            if args[0] == "curr_states":    
                print("\nCurrent states: \n")
                if self.ui._enforcer is None:
                    print("You must start the enforcer, before dumping its current states")
                    return

                #breakpoint()
                for s in self.ui._enforcer.engine.get_curr_states():
                    label = str(s)
                    if self.ui._enforcer.engine.is_state_initial(s):
                        label = f"{label} : i"
                    if self.ui._enforcer.engine.is_state_final(s):
                        label = f"{label} : f"
                    print(label)
                

            elif args[0] == "transitions":
                print("\nTransitions (*=enabled): \n")

                #breakpoint()
                #nfa : NFA = self.ui._model.get_object("nfa")
                lts : LTS = self.ui._model.get_object("lts")
                if not lts: #nfa:
                    #raise UICommand.Error("Unexpected error generating NFA from the current choreography")
                    raise UICommand.Error("Unexpected error generating LTS from the current choreography or MPST")

 
                is_current_state = lambda s: s == lts.initial #nfa.initial

                if self.ui._enforcer is not None:
                    #is_current_state = lambda s: self.ui._enforcer.engine.is_state_current(s)
                    is_current_state = lambda states: self.ui._enforcer.engine.some_state_is_current(states)

##                if self.ui._enforcer is None:
##                    print("You must start the enforcer, before dumping its transitions")
##                    return
   
                #breakpoint()
                #for t in self.ui._enforcer.engine.get_transitions():
                for t in lts.transitions: #nfa.transitions:

                    t_repr = str(t)
                    #if self.ui._enforcer.engine.is_state_current(t.source):

                    #breakpoint()
                    if is_current_state(t.source.states):
                        t_repr = f" * {t_repr}"
                    else:
                        t_repr = f"   {t_repr}"

                    print(t_repr)

            elif args[0] == "states":
                print("\nStates (*=current, i=initial, f=final) : \n")
                if self.ui._enforcer is None:
                    print("You must start the enforcer, before dumping its states")
                    return

                for s in sorted(map(lambda s: s.id, self.ui._enforcer.engine.get_all_states())):
                    label = str(s)

                    if self.ui._enforcer.engine.is_state_initial(s):
                        label = f"{label} : i"

                    if self.ui._enforcer.engine.is_state_final(s):
                        label = f"{label} : f"

                    if self.ui._enforcer.engine.is_state_current(s):
                        label = f" * {label}"
                    else:
                        label = f"   {label}"

                    print(label)


            elif args[0] == "buffer":
                print("\nBuffer: \n")
                if self.ui._enforcer is None:
                    print("You must start the enforcer, before dumping its buffer")
                    return

                bitems = self.ui._enforcer.engine.get_buffer_items() or []
                #for actor,message,precondition,knowledge in bitems:
                for precondition, (actor, action, message), knowledge in bitems:
                    msg = f"* {precondition or 'T'} -> ({actor},{action},{message})({knowledge or 'nil'})"
                    print(msg)
            
            elif args[0] == "rei":
                rei : REI = self.ui._model.get_object("rei")

                if not rei:
                    raise UICommand.Error("You must load a REI, before dumping it")

                print("\nREI: \n")
#                print(self.ui._rei)
#                print(c.to_rei())
                print(rei)

            elif args[0] == "nfa":
            #elif args[0] == "lts":

                c : Choreography = self.ui._model.get_object("choreography")
                if not c:
                    raise UICommand.Error("You must load a choreography, before dumping its nfa")


                nfa : NFA = self.ui._model.get_object("nfa")
                if not nfa:
                    raise UICommand.Error("Unexpected error generating NFA from the current choreography")

                #optimize = len(args) > 1 and args[1] == "reduced"
                
                #nfa = c.to_nfa(optimize=optimize)

                print("\nNFA: \n")
#                g = self.ui._nfa.to_dot()   
                g = nfa.to_dot()   
                print(g)
                print("\nEvent dictionary: \n")
#                for k,v in self.ui._nfa.event_dictionary.items():
                for k,v in nfa.event_dictionary.items():
                    print(f" {k} : {v}")

                print(f"\nNo. states: {len(nfa.states)}\n")
                print(f"\nNo. transitions: {len(nfa.transitions)}\n")
                print(f"\nNo. events: {len(nfa.event_dictionary)}\n")

                #breakpoint()
                filename_prefix = args[1] if len(args) > 1 else "dump_nfa_" + c.name

                filename_dot = filename_prefix + ".dot"
                filename_png = filename_dot + ".png"
            
                counter = 1
                while os.path.exists(filename_dot) or os.path.exists(filename_png):
                    #filename_prefix = f"{filename_prefix}_{counter}"
                    filename_dot = f"{filename_prefix}_{counter}.dot"
                    filename_png = f"{filename_prefix}_{counter}.png"
                    counter = counter + 1
                    #filename_dot = filename_prefix + ".dot"
                    #filename_png = filename_dot + ".png"
        
                #g.save(filename_dot)
                g.render(filename_dot, format="png", view=True)
                print(f"Graph saved to files: {filename_dot} | {filename_png}")
                    

            elif args[0] == "instance":

                ri = self.ui._model.get_object("ri")
                if not ri:
                    if len(args) > 1:
                        ri = RunningInstance.objects.filter(pk=args[1]).first()
                        if not ri:
                            print(f"No running instance found with id={args[1]}")
                    else:
                        print("No running instance and you have not specified a Running Instance id")
                    
                if ri:
                    in_events = " ".join(ri.input_events) if ri.input_events else ""
                    out_events = " ".join(ri.output_events) if ri.output_events else ""

                    #breakpoint()
                    
                    print(f"Engine        : {ri.engine_type}({ri.id})")
                    print(f"ID            : {ri.id}")
                    print(f"Choreography  : {ri.choreography}")
                    print(f"REI           : {ri.rei}")
                    print(f"Running       : {ri.running}")
                    print(f"Exec. started : {ri.execution_started or 'N/N'}")
                    print(f"Exec. ended   : {ri.execution_ended or 'N/N'}")
                    print(f"Input         : {in_events}")
                    print(f"Output        : {out_events}")
                    print(f"Buffer        : {ri.buffer}")
                    print(f"KB            : {ri.kb}")

            elif args[0] == "input":
    
                ri = self.ui._model.get_object("ri")
                in_events = " ".join(ri.input_events) if ri and ri.input_events else "N/N"
                print(in_events)

            elif args[0] == "output":

                ri = self.ui._model.get_object("ri")
                out_events = " ".join(map(str, ri.output_events)) if ri and ri.output_events else "N/N"
                print(out_events)

            else:
                print(f"Option not recognized: {' '.join(args)}")

class CmdStats(UICommand):

    _description = "Print statistics collected during execution"

    def execute(self, *args, **kwargs):
        if self.ui._enforcer is None:
            raise UICommand.Error("You must start the enforcer, before getting statistics")

        if not self.ui._enforcer._onChain:
            raise UICommand.Error("Statistics for off-chain Engine are not available.")

        self.ui.__print_stats()
        """if (args[0] == "-save"):
            with open(f'test_ganache.csv', 'a', encoding="utf-8") as f:
                f.write(tabulate(self._stats, headers=["Transaction", "Contract Address", "Gas Used", "Cost (Eth)", "Execution Time (s)", ""],tablefmt="tsv"))
                f.write("\n")"""

class CmdHistory(UICommand):

    def execute(self, *args, **kwargs):
        if self.ui._enforcer is None:
            raise UICommand.Error("You must start the enforcer, before getting statistics")

        for h in self.ui._enforcer.history:
            for key, value in h.items():
                print(f"{key} : {value}")
            print("\n")
 

class CmdSave(UICommand):

    def get_completions(self):
        return {
            "nfa": None
        }
        
    def execute(self, *args, **kwargs):
        

        n_args = len(args)
        
        if n_args == 0:
            print("Please, specify an argument")

        elif args[0] == "nfa":

            if n_args < 2:  
                print("Please, provide the output directory argument")
            elif n_args < 3:
                print("Plase, provide the filename argument")
            elif n_args < 4:
                print("Please, provide the format argument")
        
            else:
    
                outdir = args[1]
                format = args[3]
                filename = f"{args[2]}.gv"
                outfile = f"{args[2]}.{format}"

                #breakpoint()
                if not self.ui._enforcer:
                    raise UICommand.Error(f"Enforcer not started, yet")

                g = self.ui._enforcer._engine._nfa.to_dot()
                g.render(directory=outdir, filename=filename, outfile=outfile, format=format)
                print(f"NFA saved as {filename} and {outfile}")

        else:
            print("Arguments not recognized")


class CmdEnvReset(UICommand):

    _description = "Clean the environment and reset the status of the tool"

    def execute(self, *args, **kwargs):

        resp = input("Are you sure you want to reset the environment of the tool? [y/N]")
        if resp.lower() == "y": 
            self.ui._env = {}         
            self.ui._model = Model()

class CmdEnv(UICommand):

    _description = "Get/Set/List the environment and model variables"

    def get_completions(self):
        d = {}
        for k,v in self.ui.env:
            d[k] = None

        for n in self.ui._model.names:
            d[n] = None

        return d

    def execute(self, *args, rest=""): #**kwargs):

        n_args = len(args)
        
        if n_args == 0:

            all_keys = list(self.ui.env_keys) + list(self.ui._model.names)

            max_len = max(map(len, all_keys), default=0) + 3
            for k,v in self.ui.env:
                v = self.ui.display_env(k)
                print(f"{k.ljust(max_len,'.')} = {v}")

            for n in self.ui._model.names:
                v = self.ui._model.get_object(n)
                print(f"{n.ljust(max_len,'.')} = {v}")

        elif n_args == 1:
            k = args[0]
            v = self.ui.get_env(k, default=self.ui._model.get_object(k))
            print(f"{k} = {v}")

        elif n_args > 1:

            k = args[0]
            if not rest:
                raise Exception(f"Unexpected command: missing value for key: {k}")

            if k in self.ui._model.names:
                raise Exception(f"Cannot set value of model variable: {k}. They are managed by the tool")

            value = rest.replace(k, "").strip()

            self.ui.set_env(k, value)
#            print(f"Attribute not recognized ({args[0]}). Available attributes: {', '.join(self.get_completions().keys())}")

class CmdEnvUnset(UICommand):

    _description = "Un-set an environment or model variable"

    def execute(self, *args, **kwargs):
        n_args = len(args)
        if n_args == 0:
            raise Exception("Missing the name of the variable to be reset")

        k = args[0]
        if k in self.ui._model.names:
            self.ui._model.unset_object(k)
        else:
            self.ui.unset_env(k)

class UI:

    PROMPT_ENFORCER = "+> "
    PROMPT_CLI = ">> "
    PROMPT_HISTORY_CLI = os.path.join(Path.home(), ".choen_cli")
    PROMPT_HISTORY_ENFORCER = os.path.join(Path.home(), ".choen_enforcer")


    def __init__(self, *args, **kwargs):
        self._registry = {
            "init"  : CmdInit(self), #self.cmd_init,
            "list"  : CmdListChoreographies(self), #self.cmd_list,
            "list_choreographies"  : CmdListChoreographies(self), #self.cmd_list, # FS redundant but more familiar name
            "list_instances": CmdListInstances(self), 
            "clear" : CmdClear(self),
            "rm"    : CmdRemove(self), #self.cmd_remove,
#            "load"  : CmdLoadChoreography(self), #self.cmd_load,
            "open": CmdOpenFile(self),
            "load_mpst"  : CmdLoadMPST(self), #self.cmd_load, # FS redundant but more familiar name
            "load_choreography"  : CmdLoadChoreography(self), #self.cmd_load, # FS redundant but more familiar name
            "load_instance": CmdLoadInstance(self), 
            "log" : CmdLogOnOff(self), # self.cmd_start,
            "start" : CmdStart(self), # self.cmd_start,
            "stop"  : CmdStop(self), #self.cmd_stop,
            "pause"  : CmdPause(self), #self.cmd_stop,
            "debug" : CmdDebug(self), #self.cmd_debug,
            "script" : CmdScript(self), #self.cmd_debug,
            "set_filter": CmdSetFilter(self), 
            "step" : CmdStep(self), #self.cmd_debug,
            "replay" : CmdReplay(self), #self.cmd_debug,
            "help"  : CmdHelp(self), #self.cmd_help,
            "dump"  : CmdDump(self), #self.cmd_dump,
            "smooth"  : CmdSmooth(self), #self.cmd_dump,
            "random"  : CmdRandom(self), #self.cmd_dump,
            "exit"  : CmdQuit(self), #self.cmd_quit,
            "quit"  : CmdQuit(self), #self.cmd_quit
            "stats" : CmdStats(self),
            "history": CmdHistory(self),
            "save"  : CmdSave(self),
            "env"   : CmdEnv(self),
            "env_unset": CmdEnvUnset(self),
            "env_reset": CmdEnvReset(self),
            "load_config"   : CmdLoadConfiguration(self),
            "get_balance"   : CmdGetBalance(self),
            "build_contracts"   : CmdBuildContracts(self),
        }
#        self._running_instances = {}
        self._model = Model()
#        self._enforcer = None
#        self._running = False
#        self._rei = None
#        self._nfa = None
        self._debug = False #True
        self._stats = []
        self._env = {
            "ONCHAIN_URL": settings.ONCHAIN_URL,
            "ONCHAIN_CHAIN_ID": settings.ONCHAIN_CHAIN_ID,
            "ONCHAIN_ADDRESS": settings.ONCHAIN_ADDRESS,
            "ONCHAIN_PRIVATE_KEY": settings.ONCHAIN_PRIVATE_KEY,
        }

        if not os.path.exists(self.PROMPT_HISTORY_ENFORCER):
            Path(self.PROMPT_HISTORY_ENFORCER).touch(mode=0o666, exist_ok=True)

        if not os.path.exists(self.PROMPT_HISTORY_CLI):
            Path(self.PROMPT_HISTORY_CLI).touch(mode=0o666, exist_ok=True)

        cli_completer = self._get_cli_completer()
        enforcer_completer = self._get_enforcer_completer()

        self._session_enforcer = prompt_toolkit.PromptSession(self.PROMPT_ENFORCER, history=FileHistory(self.PROMPT_HISTORY_ENFORCER), completer=enforcer_completer)
        self._session_cli = prompt_toolkit.PromptSession(self.PROMPT_CLI, history=FileHistory(self.PROMPT_HISTORY_CLI), completer=cli_completer)

    @property
    def ri(self):
        return self._model.get_object("ri")

    @property
    def _enforcer(self):
        ri = self._model.get_object("ri")
        return ri.enforcer if ri else None

    @property
    def _running(self):
        ri = self._model.get_object("ri") 
        return ri.running if ri else False

    @property
    def _rei(self):
        ri = self._model.get_object("ri")
        return ri.rei if ri else None

    @property
    def _nfa(self):
        ri = self._model.get_object("ri")
        return ri.nfa if ri else None

    @property
    def env(self):
        return self._env.items()

    @property
    def env_keys(self):
        return self._env.keys()

    def _expand(self, text):

        if not isinstance(text, str):
            return text

        ctx = { k : str(v) for k,v in self._env.items() }
        ctx["NOW"] = datetime.now().isoformat()
    
        #breakpoint()
        text = re.sub(r'{([^}]+)}', lambda k: ctx.get(k.group(1).upper(), "")  ,text) #str(ctx[v]), text)
        return text       

    def display_env(self, key, default=None):

        v = self.get_env(key, default)
        if "PRIVATE" in key and v is not None:
            v = "*" * len(v) # hide private variables

        return v

    def get_env(self, key, default=None):
        #breakpoint()
        value = self._env.get(key.upper(), default) or default

        return self._expand(value)

    def unset_env(self, key):
        if key in self._env:
            del self._env[key]

    def set_env(self, key, value):
        self._env[key.upper()] = self._expand(value)

    def has_env(self, key):
        return key in self._env


    def _get_enforcer_completer(self):
        d = {}
        for n,cmd in self._registry.items():
            d[f"/{n}"] = cmd.get_completions()

        return NestedCompleter.from_nested_dict(d)

    def _get_cli_completer(self):
        d = {}
    
        for n,cmd in self._registry.items():
            d[n] = cmd.get_completions()

#        print("CLI completer")
#        print(d)
        return NestedCompleter.from_nested_dict(d)
    
    def set_debug(self, debug: bool):
        self._debug = debug

    # DEBUG LOG
    def _debug_log(self, text):
        if self._debug:
            print(text)

    def __print_stats(self):
        print(tabulate(self._stats, headers=["Transaction", "Contract Address", "Gas Used", "Cost (Eth)", "Execution Time (s)", ""],tablefmt="fancy_grid"))
        print("\n")
        """gas_used = []
        cost = []
        execution_time = []
        for row in self._stats:
            gas_used.append(row[2])
            cost.append(row[3])
            execution_time.append(row[4])
        print("Avg (Gas Used): ", round(statistics.mean(gas_used), 5))
        print("SD (Gas Used): ", round(statistics.stdev(gas_used), 5))
        print("Avg (Cost): ", statistics.mean(cost), " Eth")
        print("SD (Cost): ", statistics.stdev(cost), " Eth")
        print("Avg (Execution time): ", round(statistics.mean(execution_time), 5), " s")
        print("SD (Execution time): ", round(statistics.stdev(execution_time), 5), " s")"""


    def prompt(self, line=None):
        userin = None
        if line:
            userin = prompt_toolkit.prompt(line)
        else:
            if self._running: #enforcer:
                userin = self._session_enforcer.prompt()
            else:
                userin = self._session_cli.prompt()

        return userin


    def consume(self, userin):
        #self._debug_log(f"(* Consume user input: '{userin}' *)")
#        if not self._enforcer or userin[0] == "/":

        assert len(userin) > 0
        if not self._running or userin[0] == "/":
            if userin[0] == "/":
                userin = userin[1:]

            return self._consume_command(userin)
        else:
            return self._consume_events(userin)

    def _consume_command(self, userin : str):

        #userin_parts = userin.split(" ")
        userin_parts = userin.split(" ", 1) # split only the first item

        cmd = userin_parts[0]
        #cmd_args = userin_parts[1:]

        rest = None
        cmd_args = []

        if len(userin_parts) > 1:
            rest = userin_parts[1] 
            cmd_args = rest.split(" ")

        #print(f"Execute: {cmd}")
        handler = self._registry.get(cmd, None)

        if handler:
            try:
                handler.execute(*cmd_args, rest=rest)
            except UICommand.Error as err:
                print(f"Command error: {err}")
        else:
            print(f"ERROR: Command not recognized: {cmd} {' ' .join(cmd_args)}")


    def _consume_events(self, event_stream : str): #userin : str):

        assert self._enforcer is not None
        assert self._running is not None

        try:
            #breakpoint()
            iscan = InputScanner(event_stream)
    
            while not iscan.eof:        
                event = iscan.scan_input()

                self.ri.append_input(event)

                #breakpoint()
                self._debug_log(f"\n** Process input: {event} ... **")
                out = self._enforcer.process_input(event)
                #self._stats = self._enforcer._engine.stats
            
                if out:
                    self._debug_log(f"\nOutput message: {out}\n")
                    self.ri.append_output(out)

                self._debug_log(f"** Process completed. **\n")
                
                self._debug_log("\n** Checking for usable messages in buffer ...")
                while True:
                    out1 = self._enforcer.process_check()
                    if out1:
                        self._debug_log(f"\nOutput message: {out1}\n")
                        self.ri.append_output(out1)
                    else:
                        break            
                self._debug_log("** Checking completed. **\n")
    

        finally:        
            if self._enforcer.ended():
                self._debug_log("(* Ended *)")
                #print("\n")
                #self.__print_stats()       
                #self._enforcer = None
                #self._rei = None
                #self._running = False
                self.ri.stop()
            else:
                self.ri.save()


    def __enter__(self):
        return self


    def __exit__(self, *args, **kwargs):
        print(f"Good bye :-)")
        pass


def cli(*args, **kwargs):

    with UI() as ui:

        while True:
            try:
                userin = ui.prompt().strip()
                if not userin:  
                    continue
                ui.consume(userin)
            except (KeyboardInterrupt): 
                # CTRL+C
                continue
            except (EOFError, ):
                # CTRL+D
                break
            except Exception as e:
                traceback.print_exc()

