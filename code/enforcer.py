#from distutils.log import debug
from django.utils import timezone
from django.db import transaction
import glob
import json
from tracemalloc import start
import nfa
import traceback
import sys
import os
import re
from generator import SmartContractGenerator
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
from engine.models import Contract, Configuration, RunningInstance, Engine, EngineOnChain, EngineOffChain

import random
import string


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


    # PROCESSORS
    def process_input(self, event): #event_stream : str):

        num_states_pre = self._engine.get_num_states() #en(self._curr_states)
        out = self._engine.process_input(event)
        nd_factor = (self._engine.get_num_states() - num_states_pre) / num_states_pre
        
        #self._debug_log(f"(* Non-determinism factor: {nd_factor} *)")
        
        return out
        
         


    def process_check(self):
        out = None
        try:
            out = self._engine.process_check()

        except Exception:
            pass

        return out

    class NoMessageFound(Exception):
        pass

from enforcer import *
from bpmn_parser.models import *


class Model:

    def __init__(self):
        self._store = {}

    def add_object(self, name, obj):
        self._store[name] = obj

    def get_object(self, name):
        return self._store.get(name, None)

class UICommand:

    def __init__(self, ui):
        assert isinstance(ui, UI)
        self._ui = ui

    @property
    def ui(self):
        return self._ui

    def get_completions(self):
        return None

    def execute(self, *args, **kwargs):
        raise Exception("You must implement this")


class CmdInit(UICommand):

    def execute(self, *args, **kwargs):

        choreographies = [
            ("diagram", "diagram.bpmn", ),
            ("diagram_minimal", "diagram_minimal.bpmn"),
            ("diagram_basic", "diagram_basic.bpmn"),
            ("diagram_gateways", "diagram_gateways.bpmn", ),
            ("diagram_gateways_mismatch", "diagram_gateways_mismatch.bpmn", ),
            ("diagram_gateways_dangling", "diagram_gateways_dangling.bpmn", ),
            ("diagram_gateways_nested", "diagram_gateways_nested.bpmn", ),
            ("diagram_gateways_nested_intermediate", "diagram_gateways_nested_with_intermediate_task.bpmn", ),
            ("diagram_gateways_nested_inclusive", "diagram_gateways_nested_inclusive.bpmn", ),
            ("diagram_gateways_nested_dangling", "diagram_gateways_nested_dangling.bpmn", ),
            ("diagram_construction_industry", "diagram_construction_industry.bpmn"),
            ("diagram_patient_doctor","diagram_patient_doctor.bpmn"),
            ("diagram_incident_management", "diagram_incident_management.bpmn")
 
        ]

        for name, filename in choreographies:
            attribs = {
                "name": name,
                "resource": os.path.join(settings.MEDIA_ROOT, filename),
            }
            
            c, created = Choreography.objects.get_or_create(name=name, defaults=attribs)
            if created:
                print(f"Choreography {name} imported ...")
            else:
                print(f"Choreography {name} already exists ...")


class CmdDebug(UICommand):

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

    def execute(self, *args, **kwargs):
        raise KeyboardInterrupt()


class CmdHelp(UICommand):
    def execute(self, *args, **kwargs):
        print("Available commands: ")
        print(", ".join(sorted(self.ui._registry.keys())))


##class CmdEnv(UICommand):
##
##    def execute(self, *args, **kwargs):
##        for k,v in self.ui.env:
##            print(f"{k} = {v}")
##

class CmdListInstances(UICommand):

    def execute(self, *args, **kwargs):

        print("Running instances:")
        instances = RunningInstance.objects.all()
        if len(instances) == 0:
            print("(* none *)")
        else:
            for ri in RunningInstance.objects.all():
                print(f" * {ri.id} : {ri}")

class CmdListChoreographies(UICommand):

    def execute(self, *args, **kwargs):

        print("Available choreographies:")
        items = Choreography.objects.all().order_by("name")

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


class CmdClear(UICommand):

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
    

class CmdBuildContracts(UICommand):

    def execute(self, name=None, *args, **kwargs):

        c : Choreography = self.ui._model.get_object("choreography")

        if not c:
            print("No choreography loaded, yet. Cannot continue")
            return

        nfa = c.to_nfa()

        self.compile(nfa)

    
    def compile(self, nfa):

        debug = True
        smartContractGenerator: SmartContractGenerator = SmartContractGenerator(nfa)
        compiled_sol = smartContractGenerator.createSmartContract().compile(debug)
 
class CmdLoadChoreography(UICommand):

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
            self.ui._model.add_object("choreography", c)
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
            c.to_nfa()
        except Exception as err:
            print(f"KO Choreography {cho_name} : error extracting NFA ({err}), cannot import ...")
            return

        self.ui._model.add_object("choreography", c)
        if created:
            print(f"OK Choreography {cho_name} : imported and loaded ...")
        else:
            print(f"OK Choreography {cho_name} : already exists and has been loaded ...")
 
 

class CmdStop(UICommand):
    
    def execute(self, *args, **kwargs):

        ri : RunningInstance = self.ui._model.get_object("ri")

        if not ri:
            raise Exception("No running instance to stop")

        ri.stop()
 
class CmdPause(UICommand):
  
    def execute(self, *args, **kwargs):

        ri : RunningInstance = self.ui._model.get_object("ri")

        if not ri:
            raise Exception("No running instance to pause")

        self.ui._model.add_object("ri", None)

class CmdStart(UICommand):

    def setup_onchain_running_instance(self, ri, contract_address): #automaton, contract_address, conf): #onchain_url, onchain_chain_id, onchain_address, onchain_private_key):
        # detect whether a configuration exists with given parameters, otherwise save it
        #engine = EngineOnChain(automaton, conf.url, conf.chain_id, conf.address, conf.private_key)

        if not ri.blockchain_configuration:
            raise Exception("The running instance is supposed to have a non-null blockchain configuration at this stage")

        try:
            engine = ri.engineonchain
    
            if not engine:
                raise Exception("Engine not set")

            if not engine.nfa:
                engine.set_nfa(automaton)

        except Exception:
            engine = EngineOnChain.create_engine(ri) #automaton, conf)

        #breakpoint()
        if contract_address:

            if ri.engineonchain and ri.engineonchain.contract_enforcer and ri.engineonchain.contract_enforcer.contract_address != contract_address:
                raise Exception(f"The running instance ({ri}) is linked to a different enforcer smart contract. Passed: {contract_address}")

            # 2b1. search nfa address, if enforcer address is given (use the enforcer/engine of previous step)
#            c_enforcer = Contract.objects.filter(contract_address=contract_address).first()
#            if c_enforcer:
#                raise Excetpion(f"The specified smart contract ({c_enforcer}) already exists in the database. Associated running instance: {c_enforcer.running_instance}")
#
#            c_enforcer = Contract()
#            c_enforcer.label = "enforcer"
#            c_enforcer.contract_address = contract_address
            engine.attach_smart_contracts(contract_address)

        else:

            # 2a. deploy new contracts if no address is given
            #scg = SmartContractGenerator(automaton)
            #compiled = scq.createSmartContract().compile(True) # True => debug mode
            engine.deploy_smart_contracts()


        # 3. store contracts with attached/deploy smart contract addresses, abis, 
        #    and bytecodes

        sc_enforcer, sc_enforcer_created = Contract.objects.get_or_create(
            contract_address=engine._enforcer_address, 
            defaults={
                "abi":engine._enforcer_abi, 
                "bytecode":engine._enforcer_bytecode,
                "label":"enforcer"
            })

        #if not sc_enforcer_created and sc_enforcer.running_instance != ri:
        #    raise Exception(f"The smart contract ({sc_enforcer}) is already attached to a different running instance: {sc_enforcer.running_instance}")

        sc_nfa, sc_nfa_created = Contract.objects.get_or_create(
            contract_address=engine._nfa_address, 
            defaults={
                "abi":engine._nfa_abi, 
                "bytecode":engine._nfa_bytecode,
                "label":"nfa"
            })

        #if not sc_nfa_created and sc_nfa.running_instance != ri:
        #    raise Exception(f"The smart contract ({sc_nfa}) is already attached to a different running instance: {sc_nfa.running_instance}")
 
        if engine.contract_enforcer != sc_enforcer or engine.contract_nfa != sc_nfa:
            engine.contract_enforcer = sc_enforcer
            engine.contract_nfa = sc_nfa
            engine.save()

        #ri.blockchain_configuration = conf
        enforcer = Enforcer(engine)
        ri.set_enforcer(enforcer)

        # 5. link contracts to running instance (and save the contracts again)
        #sc_enforcer.running_instance = ri
        #sc_nfa.running_instance = ri
        #with transaction.atomic():
        ri.save()
        #sc_enforcer.save()
        #sc_nfa.save()

        return ri


    def setup_offchain_running_instance(self, ri): #, automaton):
        #engine = EngineOffChain(automaton)

        #breakpoint()
        automaton = ri.choreography.to_nfa()

        try:
            engine = ri.engineoffchain

            if not engine:
                raise Excepion("Engine off-chain not set yet")

            if not engine.nfa:
                engine.set_nfa(automaton)

        except Exception:
            engine = EngineOffChain.create_engine(ri) #automaton)

        enforcer = Enforcer(engine)
        ri.set_enforcer(enforcer)
        ri.save()
        return ri


    @transaction.atomic
    def execute(self, contract_address=None, *args, **kwargs):

        #breakpoint()
        cho : Choreography = self.ui._model.get_object("choreography")

        if len(args) > 0:
            cho = Choreography.objects.get(name=args[0])

        if not cho:
            raise Exception("You must load a choreography or start a choreography")

        if not os.path.exists("log.txt"):
            with open(f'log.txt', 'w', encoding="utf-8") as f:
                f.write("Run;Blockchain;Time;Transaction;Contract Address;Gas Used;Cost;Execution Time\n")
    
        #breakpoint()

        # 0. create a stub of running instance
        ri = RunningInstance()
        ri.choreography = cho
        ri.label = cho.name
#        ri.running = True   
#        ri.execution_started = timezone.now() # TODO this is ok when starting a new instance; when attaching a running smart contract, one should try to find the time when the deployment transaction was validated
 
        # 1. create a pair enforcer/engine
        #enforcer = None
 
        automaton = cho.to_nfa()

        onchain_url = self.ui.get_env("ONCHAIN_URL")
        onchain_chain_id = int(self.ui.get_env("ONCHAIN_CHAIN_ID", 0))
        onchain_address = self.ui.get_env("ONCHAIN_ADDRESS")
        onchain_private_key = self.ui.get_env("ONCHAIN_PRIVATE_KEY")
 
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

            ri.blockchain_configuration = conf
            ri.save()

            self.setup_onchain_running_instance(ri, contract_address) #automaton, contract_address, conf) #onchain_url, onchain_chain_id, onchain_address, onchain_private_key)     
    
        else:

            if contract_address:
                raise Exception(f"You specified a smart contract address for the enforcer, but you did not provide your blockchain configuration in the /env")
    
            ri.save()
            ri = self.setup_offchain_running_instance(ri) #, automaton)
   
        self.ui._model.add_object("ri", ri)

##        # TODO refactor the following
##
##        ri : RunningInstance = RunningInstance()
##        ri.choreography = c
##        ri.label = c.name
## 
##        onchain_url = self.ui.get_env("ONCHAIN_URL")
##        onchain_chain_id = int(self.ui.get_env("ONCHAIN_CHAIN_ID"))
##        onchain_address = self.ui.get_env("ONCHAIN_ADDRESS")
##        onchain_private_key = self.ui.get_env("ONCHAIN_PRIVATE_KEY")
## 
##        if onchain_url and onchain_chain_id and onchain_address and onchain_private_key:
##    
##            c_list = Configuration.objects.filter(url=onchain_url, chain_id=onchain_chain_id, address=onchain_address, private_key=onchain_private_key)
##    
##            if len(c_list) > 0:
##                conf = c_list[0]
##            else:
##
##                suffix = datetime.now().strftime("%Y%m%d_%H%M%S")
##
##                conf = Configuration()
##                conf.url = onchain_url
##                conf.chain_id = onchain_chain_id
##                conf.address = onchain_address
##                conf.private_key = onchain_private_key
##                conf.label = f"New configuration {suffix}"
##                conf.save()
##    
##            ri.blockchain_configuration = conf
##            ri.engine_type = RunningInstance.EngineType.ON_CHAIN
##
##        if contract_address:
##            if ri.engine_type != RunningInstance.EngineType.ON_CHAIN:
##                raise Exception("Cannot attach to a running contract address with off-chain enforcer engines. Please, provide an on-chain configuration on your /env")
##
##            ri.attach(contract_address)
##        else:
##            ri.start() # NB the start method, also saves it
##
##        if not ri.enforcer:
##            raise Exception(f"The start/attach procedure should have set an enforcer at this stage. Cannot continue")
##
##        self.ui._model.add_object("ri", ri)
##
##        #ri_enforcer = str(ri.enforcer) if ri.enforcer else "N/N"
##        print(f"Enforcer: {ri.enforcer}") 
##
##        if isinstance(ri.enforcer, EngineOnChain):
##            self.ui._debug_log(f"\nGas price:  {ri.enforcer._engine.w3.eth.gas_price} Wei")
##
##        if ri.enforcer.ended():
##            ri.stop()
##            self.ui._debug_log("(* Ended *)")
##
##


#class CmdLoadInstance(UICommand):   
class CmdLoadInstance(CmdStart):

    def get_completions(self):
        d = {}

        for ri in RunningInstance.objects.all():
            d[str(ri.id)] = None

        #print(f"Completions: {d}")
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

                    self.setup_onchain_running_instance(ri, contract_address) # automaton, contract_address, ri.blockchain_configuration)

                else:
                    self.ui.set_env("ONCHAIN_URL", None)
                    self.ui.set_env("ONCHAIN_CHAIN_ID", None)
                    self.ui.set_env("ONCHAIN_ADDRESS", None)
                    self.ui.set_env("ONCHAIN_PRIVATE_KEY", None)

                    self.setup_offchain_running_instance(ri) #, automaton)


                # 3. call the setup_onchain/offchain_engine

                # 4. set the running instance
                self.ui._model.add_object("ri", ri)
                
            except RunningInstance.DoesNotExist as e:
                print(f"Cannot find running instance {ri_id}")
                 


class CmdRandom(UICommand):

    def execute(self, *args, **kwargs):

        ri = self.ui._model.get_object("ri")
        if ri:
    
 
            actor = random_string(10)
            msg = random_string(10)
            action = random.choice(["?","!"])
            random_event = f"{actor}{action}{msg}"
            ri.enforcer.process_input(random_event)

class CmdDump(UICommand):

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

        if len(args) == 0:
            print("Please specify an argument: dump <curr_states|states|transitions|buffer|rei>")
        else:
            if args[0] == "curr_states":    
                print("\nCurrent states: \n")
                if self.ui._enforcer is None:
                    print("You must start the enforcer, before dumping its current states")
                    return

                for s in self.ui._enforcer.engine.get_curr_states():
                    label = str(s)
                    if self.ui._enforcer.engine.is_state_initial(s):
                        label = f"{label} : i"
                    if self.ui._enforcer.engine.is_state_final(s):
                        label = f"{label} : f"
                    print(label)
                

            elif args[0] == "transitions":
                print("\nTransitions (*=enabled): \n")
                if self.ui._enforcer is None:
                    print("You must start the enforcer, before dumping its transitions")
                    return

                for t in self.ui._enforcer.engine.get_transitions():

                    t_repr = str(t)
                    if self.ui._enforcer.engine.is_state_current(t.source):
                        t_repr = f" * {t_repr}"
                    else:
                        t_repr = f"   {t_repr}"

                    print(t_repr)

            elif args[0] == "states":
                print("\nStates (*=current, i=initial, f=final) : \n")
                if self.ui._enforcer is None:
                    print("You must start the enforcer, before dumping its states")
                    return

                for s in self.ui._enforcer.engine.get_all_states():
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

                for actor,message in self.ui._enforcer.engine.get_buffer_items():
                    msg = f"* {actor}{message}"
                    print(msg)
            
            elif args[0] == "rei":
                c : Choreography = self.ui._model.get_object("choreography")

                if not c:
                    print("You must load a choreography, before dumping its rei")
                    return

                print("\nREI: \n")
#                print(self.ui._rei)
                print(c.to_rei())

            elif args[0] == "nfa":

                c : Choreography = self.ui._model.get_object("choreography")
                nfa = c.to_nfa()

                print("\nNFA: \n")
#                g = self.ui._nfa.to_dot()   
                g = nfa.to_dot()   
                print(g)
                print("\nEvent dictionary: \n")
#                for k,v in self.ui._nfa.event_dictionary.items():
                for k,v in nfa.event_dictionary.items():
                    print(f" {k} : {v}")

                #breakpoint()
                filename_prefix = args[1] if len(args) > 1 else "curr_graph"

                filename_dot = filename_prefix + ".dot"
                filename_png = filename_dot + ".png"
            
                counter = 1
                while os.path.exists(filename_dot) or os.path.exists(filename_png):
                    filename_prefix = f"{filename_prefix}_{counter}"
                    counter = counter + 1
                    filename_dot = filename_prefix + ".dot"
                    filename_png = filename_dot + ".png"
        
                #g.save(filename_dot)
                g.render(filename_dot, format="png", view=True)
                print(f"Graph saved to files: {filename_dot} | {filename_png}")
                    

            elif args[0] == "instance":

                ri = self.ui._model.get_object("ri")
                if not ri:
                    print("N/N")
                else:
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
                out_events = " ".join(ri.output_events) if ri and ri.output_events else "N/N"
                print(out_events)

            else:
                print(f"Option not recognized: {' '.join(args)}")

class CmdStats(UICommand):

    def execute(self, *args, **kwargs):
        if self.ui._enforcer is None:
            print("You must start the enforcer, before getting statistics")
            return
        if not self.ui._enforcer._onChain:
            print("Statistics for off-chain Engine are not available.")
            return
        self.ui.__print_stats()
        """if (args[0] == "-save"):
            with open(f'test_ganache.csv', 'a', encoding="utf-8") as f:
                f.write(tabulate(self._stats, headers=["Transaction", "Contract Address", "Gas Used", "Cost (Eth)", "Execution Time (s)", ""],tablefmt="tsv"))
                f.write("\n")"""

class CmdHistory(UICommand):

    def execute(self, *args, **kwargs):
        if self.ui._enforcer is None:
            print("You must start the enforcer, before getting statistics")
            return
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

                g = self.ui._enforcer._engine._nfa.to_dot()
                g.render(directory=outdir, filename=filename, outfile=outfile, format=format)
                print(f"NFA saved as {filename} and {outfile}")

        else:
            print("Arguments not recognized")


class CmdEnv(UICommand):

    def get_completions(self):
        d = {}
        for k,v in self.ui.env:
            d[k] = None
        return d

    def execute(self, *args, **kwargs):

        n_args = len(args)
        
        if n_args == 0:
#            print(f"Please, specify an argument: {self.get_completions().keys()}")
            for k,v in self.ui.env:
                if "PRIVATE" in k and v is not None:
                    v = "*" * len(v) # hide private variables

                print(f"{k} = {v}")

        elif self.ui.has_env(args[0]):
            if len(args) > 1:
                self.ui.set_env(args[0], args[1])
            else:
                v = self.ui.get_env(args[0])
                if "PRIVATE" in args[0]:
                    v = "*" * len(v)
                print(f"{args[0]} = {v}")
        else:
            print(f"Attribute not recognized ({args[0]}). Available attributes: {', '.join(self.get_completions().keys())}")


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
            "load_choreography"  : CmdLoadChoreography(self), #self.cmd_load, # FS redundant but more familiar name
            "load_instance": CmdLoadInstance(self),
            "start" : CmdStart(self), # self.cmd_start,
            "stop"  : CmdStop(self), #self.cmd_stop,
            "pause"  : CmdPause(self), #self.cmd_stop,
            "debug" : CmdDebug(self), #self.cmd_debug,
            "help"  : CmdHelp(self), #self.cmd_help,
            "dump"  : CmdDump(self), #self.cmd_dump,
            "random"  : CmdRandom(self), #self.cmd_dump,
            "exit"  : CmdQuit(self), #self.cmd_quit,
            "quit"  : CmdQuit(self), #self.cmd_quit
            "stats" : CmdStats(self),
            "history": CmdHistory(self),
            "save"  : CmdSave(self),
            "env"   : CmdEnv(self),
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

    def get_env(self, key, default=None):
        #breakpoint()
        return self._env.get(key, default)

    def set_env(self, key, value):
        self._env[key] = value

    def has_env(self, key):
        return key in self._env

#    def set_running(self, v : bool):
#        self._running = v


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

        if not self._running or userin[0] == "/":
            if userin[0] == "/":
                userin = userin[1:]

            return self._consume_command(userin)
        else:
            return self._consume_events(userin)

    def _consume_command(self, userin : str):

        userin_parts = userin.split(" ")
        cmd = userin_parts[0]
        cmd_args = userin_parts[1:]

        #print(f"Execute: {cmd}")
        handler = self._registry.get(cmd, None)

        if handler:
            handler.execute(*cmd_args)
        else:
            print(f"ERROR: Command not recognized: {cmd} {' ' .join(cmd_args)}")


    def _consume_events(self, event_stream : str): #userin : str):

        assert self._enforcer is not None
        assert self._running is not None

        try:
            #breakpoint()
            iscan = nfa.InputScanner(event_stream)
    
            while not iscan.eof:        
                event = iscan.scan_input()

                self.ri.append_input(event)

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
                userin = ui.prompt()
                ui.consume(userin)
            except (EOFError, KeyboardInterrupt):
                break
            except Exception as e:
                traceback.print_exc()

