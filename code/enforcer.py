from distutils.log import debug
import json
from tracemalloc import start
import nfa
import traceback
import sys
import os
import re
from web3 import Web3
from generator import SmartContractGenerator
import time
from tabulate import tabulate
from django.conf import settings
import statistics
from datetime import datetime
import uuid

class Engine:

    def __init__(self):
        self._debug : bool = True

    def set_debug(self, debug: bool):
        self._debug = debug

    # DEBUG LOG
    def _debug_log(self, text):
        if self._debug:
            print(text)


    def ended(self):
        raise Exception("This is an abstract method, you should implement it")

    def get_all_states(self):
        raise Exception("This is an abstract method, you should implement it")

    def get_curr_states(self):
        raise Exception("This is an abstract method, you should implement it")

    def get_transitions(self):
        raise Exception("This is an abstract method, you should implement it")

    def is_state_final(self, s):
        raise Exception("This is an abstract method, you should implement it")

    def is_state_initial(self, s):
        raise Exception("This is an abstract method, you should implement it")

    def is_state_current(self, s):
        raise Exception("This is an abstract method, you should implement it")

    def get_num_states(self):
        return len(self.get_all_states())

    def get_buffer_items(self):
        raise Exception("This is an abstract method, you should implement it")


    # RULE CONDITIONS
    def condition_rule_send(self, event):
        raise Exception("This is an abstract method, you should implement it")

    def condition_rule_receive_now(self, event):
        raise Exception("This is an abstract method, you should implement it")

    def condition_rule_receive_delayed(self, event):
        raise Exception("This is an abstract method, you should implement it")
    
    # RULE EFFECTS
    def rule_send(self, event):
        raise Exception("This is an abstract method, you should implement it")
    
    def rule_receive_now(self, event):

        raise Exception("This is an abstract method, you should implement it")

    def rule_receive_delayed(self, event):

        raise Exception("This is an abstract method, you should implement it")


class EngineOffChain(Engine):

    def __init__(self, nfa : nfa.NFA):
        assert nfa is not None, f"Expected not-null nfa to build an enforcer"
        self._nfa : nfa.NFA = nfa
        self._buffer = {}
        self._curr_states = self._nfa.e_closure(set([ self._nfa.initial.id ]))
        self._debug : bool = True
        


    @property
    def buffer(self) -> dict:
        return self._buffer

    @property
    def curr_states(self) -> str:
        return self._curr_states

    @property
    def nfa(self):
        return self._nfa

    # UTILS

    def _buffer_add(self, actor : str, message : str):

        actor_buffer = self._buffer.get(actor, {})
        message_counter = actor_buffer.get(message, 0)
        actor_buffer[message] = message_counter + 1
        self._buffer[actor] = actor_buffer

    def _buffer_remove(self, actor : str, message : str):

        actor_buffer = self._buffer.get(actor, {})
        message_counter = actor_buffer.get(message, 0)
        assert message_counter >= 0

        if message_counter <= 0:
            raise Exception(f"No message {message} to remove for actor {actor}")
        
        actor_buffer[message] = message_counter - 1
        self._buffer[actor] = actor_buffer

    
    def _buffer_find_usable_message(self):
        found = None

        for actor, actor_buffer in self._buffer.items():
            for message, counter in actor_buffer.items():
                if counter > 0:
                    event = f"{actor}?{message}"
                    for s in self._curr_states:
                        if self._nfa.transitions_from(s, event):
                            found = (actor, message)
                            return found
        
        raise Exception("No usable message found")

    
    # INTERFACE methods

    def ended(self):
        return self._nfa.is_final(self._curr_states)

    def get_all_states(self):
        return self._nfa.states

    def get_curr_states(self):
        return self._curr_states

    def get_transitions(self):
        return self._nfa.transitions

    def is_state_final(self, s):
        return self._nfa.is_final(s)

    def is_state_initial(self, s):  
        return self._nfa.is_initial(s)

    def is_state_current(self, s):
        if isinstance(s, nfa.State):
            s = s.id
        
        res = (s in self._curr_states)
        return res

    def get_buffer_items(self):
        items = []

        for actor,actor_buffer in self.buffer.items():
            for message,counter in actor_buffer.items():
                for i in range(counter):
                    items.append((actor, message))
        return items



    # CONDITIONS below

    def condition_rule_send(self, event):
        #return "!" in event
        m = re.match("^[^?!]+![^!?]+$", event) 
        self._debug_log(f"(* Condition rule receive send: {event} => {m} *)")
        return m is not None

    def condition_rule_receive_now(self, event):

        m = re.match("^[^!?]+\?[^!?]+$", event) 
        self._debug_log(f"(* Condition rule receive now 1st: {event} => {m} *)")
        if m is None:
            return False

        for curr in self._curr_states:
            enabled_transitions = self._nfa.transitions_from(curr, event)

            if len(enabled_transitions) > 0:
                return True

        return False

    def condition_rule_receive_delayed(self, event):    

        m = re.match("^[^!?]+\?[^!?]+$", event) 
        self._debug_log(f"(* Condition rule receive delayed: {event} => {m} *)")
        return m is not None

    # RULES below

    def rule_send(self, event):
        return event

    def rule_receive_now(self, event):

        reached = set()
        for s in self._curr_states:

            s_reached = self._nfa.read_symbol(event, s)

            if len(s_reached) == 0:
                self._debug_log(f"(* State {s} was not compatible with event {event} and has been discarded... *)")
            else:
                reached = reached.union(s_reached)
            

        self._curr_states = reached
        return event

#    def rule_receive_delayed(self, actor, message):
    def rule_receive_delayed(self, event):
        actor, message = event.split("?")
        self._buffer_add(actor, message)
        return ""

    def rule_receive_buffered(self, actor, message):
        
        assert actor in self._buffer and message in self._buffer[actor]
        
        counter = self._buffer[actor][message]

        assert counter > 0

        event = f"{actor}?{message}"

        reached = set()
        for s in self._curr_states:
            s_reached = self._nfa.read_symbol(event, s)

            if len(s_reached) == 0:
                self._debug_log(f"(* State {s} was not compatible with event {event} and has been discarded... *)")
            else:
                reached = reached.union(s_reached)
        
        self._buffer_remove(actor, message)

        nd_factor = (len(reached) - len(self._curr_states)) / len(self._curr_states)
        self._debug_log(f"(* Non-determism factor: {nd_factor} *)")
        self._curr_states = reached


        return event


class EngineOnChain(Engine):

    def __init__(self, nfa : nfa.NFA, debug_compile : bool = False):
        assert nfa is not None, f"Expected not-null nfa to build an enforcer"
        self._nfa : nfa.NFA = nfa
        self._debug : bool = True
        self._runID = uuid.uuid4()

        self._debug_log(f"\nConnecting to {settings.BLOCKCHAIN_URL} ...")
        self._w3 : Web3 = Web3(Web3.HTTPProvider(settings.BLOCKCHAIN_URL, request_kwargs={'timeout': 300}))
        self._chain_id : int = settings.CHAIN_ID
        self._debug_log("Connected.")
        
        self._address : str = settings.ADDRESS
        self._private_key : str = settings.PRIVATE_KEY

        self._stats = []

        smartContractGenerator: SmartContractGenerator = SmartContractGenerator(nfa)
        compiled_sol = smartContractGenerator.createSmartContract().compile(debug_compile)
        
        self._nfa_abi, self._nfa_bytecode = self.__get_abi_and_bytecode(compiled_sol, "NFA")
        self._enforcer_abi, self._enforcer_bytecode = self.__get_abi_and_bytecode(compiled_sol, "Enforcer")

        self._nfa_address = self.deployContractNFA(self._nfa_abi, self._nfa_bytecode)
        self._enforcer_address = self.deployContractEnforcer(self._enforcer_abi, self._enforcer_bytecode, self._nfa_address)

    @property
    def nfa(self):
        return self._nfa

    @property
    def w3(self) -> Web3:
        return self._w3
    
    @property
    def chain_id(self) -> int:
        return self._chain_id

    @property
    def address(self) -> str:
        return self._address

    @property
    def private_key(self) -> str:
        return self._private_key
    
    @property
    def stats(self) -> str:
        return self._stats

    @property
    def nfa_abi(self):
        return self._nfa_abi
    
    @property
    def nfa_bytecode(self) -> str:
        return self._nfa_bytecode

    @property 
    def nfa_address(self) -> str:
        return self._nfa_address

    @property
    def enforcer_abi(self):
        return self._enforcer_abi
    
    @property
    def enforcer_bytecode(self) -> str:
        return self._enforcer_bytecode
    
    @property
    def enforcer_address(self) -> str:
        return self._enforcer_address

    def __get_abi_and_bytecode(self, compiled_sol, contract : str):
        #get bytecode
        bytecode = compiled_sol["contracts"]["smart_contract.sol"][contract]["evm"]["bytecode"]["object"]
        
        #get abi
        abi = json.loads(compiled_sol["contracts"]["smart_contract.sol"][contract]["metadata"])["output"]["abi"]

        return abi, bytecode

    def __log(self, contractAddress, gasUsed, cost, executionTime, type = None):
        with open(f'log.txt', 'a', encoding="utf-8") as f:
                f.write(f"{self._runID};{settings.BLOCKCHAIN_URL};{datetime.now()};{type};{contractAddress};{gasUsed};{cost};{executionTime}\n")
                #f.write(tabulate(self._stats, headers=["Transaction", "Contract Address", "Gas Used", "Cost (Eth)", "Execution Time (s)", ""],tablefmt="tsv"))
                #f.write("\n")
    
    def __add_statistics(self, contractAddress, gasUsed, cost, executionTime, type = None):
        self._stats.append([type, contractAddress, gasUsed, cost, executionTime])
    
    def __sendTransaction(self, transaction):
        # Sign the transaction
        sign_transaction = self.w3.eth.account.sign_transaction(transaction, private_key = self.private_key)
        
        # Send the transaction
        tx_hash = self.w3.eth.send_raw_transaction(sign_transaction.rawTransaction)
        
        # Wait for the transaction to be mined, and get the transaction receipt
        tx_receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash)

        return tx_receipt

    def __deployContract(self, contract_name : str, abi, bytecode, address = None):
        #create the contract
        contract = self.w3.eth.contract(abi=abi, bytecode=bytecode)

        nonce =  self.w3.eth.getTransactionCount(self.address)

        start_time = time.time()
        # build transaction
        if (address == None):
            transaction = contract.constructor().buildTransaction(
            {
                "chainId": self.chain_id,
                "gasPrice": self.w3.eth.gas_price,
                "from": self.address,
                "nonce": nonce,
            }
        )
        else:
            transaction = contract.constructor(address).buildTransaction(
            {
                "chainId": self.chain_id,
                "gasPrice": self.w3.eth.gas_price,
                "from": self.address,
                "nonce": nonce,
            }
        )
        build_time = time.time() - start_time
        self._debug_log(f"\nDeploying contract {contract_name} ...")
        tx_receipt = self.__sendTransaction(transaction)
        execution_time = time.time() - start_time
        self.__add_statistics(tx_receipt.contractAddress ,tx_receipt.gasUsed, round(self.w3.fromWei(tx_receipt.gasUsed * self._w3.eth.gas_price, 'ether'),2), round(execution_time,3), f"Contract Creation")
        self.__log(tx_receipt.contractAddress ,tx_receipt.gasUsed, round(self.w3.fromWei(tx_receipt.gasUsed * self._w3.eth.gas_price, 'ether'),2), round(execution_time,3),f"Contract Creation")
        self._debug_log(f"Done! Contract deployed to {tx_receipt.contractAddress}\n")
        return tx_receipt.contractAddress


    def deployContractNFA(self, abi, bytecode):
        return self.__deployContract("NFA", abi, bytecode)
    
    def deployContractEnforcer(self, abi, bytecode, nfa_address : str):
        return self.__deployContract("Enfocer", abi, bytecode, nfa_address)


    # INTERFACE methods

    def ended(self):
        return self.w3.eth.contract(
                address = self.nfa_address,
                abi = self.nfa_abi
            ).functions.isFinal().call()

    def get_all_states(self):
        return self.w3.eth.contract(
                address = self.nfa_address,
                abi = self.nfa_abi
            ).functions.getStates().call()

    def get_curr_states(self):
        return self.w3.eth.contract(
                address = self.nfa_address,
                abi = self.nfa_abi
            ).functions.getCurrentStates().call()

    def get_transitions(self):
        return self._nfa.transitions

    def is_state_final(self, s):
        return self._nfa.is_final(s)

    def is_state_initial(self, s):  
        return self._nfa.is_initial(s)

    def is_state_current(self, s):
        if isinstance(s, nfa.State):
            s = s.id

        curr_states = self.get_curr_states()
        return s in curr_states

    def get_buffer_items(self):
        enforcer = self.w3.eth.contract(
                address = self.enforcer_address,
                abi = self.enforcer_abi
            )

        actors = enforcer.functions.getActors().call()

        messages = enforcer.functions.getMessages().call()

        items = []

        for actor in actors:
            for message in messages:
                counter = enforcer.functions.get_buffer_item(actor, message).call()
                for i in range(counter):
                    items.append((actor, message))
        return items

    #PROCESSORS
    def process_input(self, event):
        enforcer = self.w3.eth.contract(
                address = self.enforcer_address,
                abi = self.enforcer_abi
            )
        nonce = self.w3.eth.getTransactionCount(self.address)
        start_time = time.time()
        transaction = enforcer.functions.process_input(event).buildTransaction({
                        "chainId": self.chain_id,
                        "from": self.address,
                        "gasPrice": self.w3.eth.gas_price,
                        "nonce": nonce
                    })
        build_time = time.time() - start_time
        tx_receipt = self.__sendTransaction(transaction)
        execution_time = time.time() - start_time
        self.__add_statistics(tx_receipt.contractAddress ,tx_receipt.gasUsed, round(self.w3.fromWei(tx_receipt.gasUsed * self._w3.eth.gas_price, 'ether'),2), round(execution_time,3), f"Process input: {event}")
        self.__log(tx_receipt.contractAddress ,tx_receipt.gasUsed, round(self.w3.fromWei(tx_receipt.gasUsed * self._w3.eth.gas_price, 'ether'),2), round(execution_time,3), f"Process input: {event}")
        return enforcer.events.outputEvent().processReceipt(tx_receipt)

    def process_check(self):
        enforcer = self.w3.eth.contract(
                address = self.enforcer_address,
                abi = self.enforcer_abi
            )
        nonce = self.w3.eth.getTransactionCount(self.address)
        start_time = time.time()
        transaction = enforcer.functions.process_check().buildTransaction({
                        "chainId": self.chain_id,
                        "from": self.address,
                        "gasPrice": self.w3.eth.gas_price,
                        "nonce": nonce
                    })
        build_time = time.time() - start_time
        tx_receipt = self.__sendTransaction(transaction)
        execution_time = time.time() - start_time
        self.__add_statistics(tx_receipt.contractAddress ,tx_receipt.gasUsed, self.w3.fromWei(tx_receipt.gasUsed * self._w3.eth.gas_price, 'ether'), round(execution_time,3), f"Process check")
        self.__log(tx_receipt.contractAddress ,tx_receipt.gasUsed, self.w3.fromWei(tx_receipt.gasUsed * self._w3.eth.gas_price, 'ether'), round(execution_time,3), f"Process check")
        return enforcer.events.outputEvent().processReceipt(tx_receipt)


class Enforcer:

    def __init__(self, nfa : nfa.NFA, onChain : bool = True):
        assert nfa is not None, f"Expected not-null nfa to build an enforcer"
        self._debug : bool = True
        self._onChain : bool = onChain
        
        self._history = []

        if onChain:
            self._engine = EngineOnChain(nfa, False)
        else:
            self._engine = EngineOffChain(nfa)

        self._append_history("",self._engine.get_curr_states(), self._engine.get_buffer_items())   

    @property
    def engine(self):
        return self._engine
    
    @property
    def history(self):
        return self._history

    # DEBUG LOG

    def set_debug(self, debug: bool):
        self._debug = debug


    def _debug_log(self, text):
        if self._debug:
            print(text)

    def _append_history(self, event : str, curr_states : list, buffer : list):
        self.history.append({
            "event" : event, 
            "curr_states" : curr_states, 
            "buffer" : buffer}
        )

    def ended(self):
        return self._engine.ended()


    # PROCESSORS

    def process_input(self, event): #event_stream : str):
        out = None
        if (self._onChain):
            logs = self._engine.process_input(event)
            self._debug_log(logs[0].args.debug)
            out = logs[0].args.messageOut
            out = None if out == "None" else out
        else:
            #out = None
            num_states_pre = self._engine.get_num_states() #en(self._curr_states)

    #       if "!" in event:
                # actor, message = event.split("!")
            if self._engine.condition_rule_send(event):
                out = self._engine.rule_send(event)

    #        elif "?" in event:
    #            actor, message = event.split("?")
            elif self._engine.condition_rule_receive_now(event):
                    out = self._engine.rule_receive_now(event)

            elif self._engine.condition_rule_receive_delayed(event):
                    # TODO add check that the message may actually be consumed afterwards;
                    # without this check, it does not make sense to implement the rule "Cannot receive" 
                #out = self._engine.rule_receive_delayed(actor, message)
                out = self._engine.rule_receive_delayed(event)
            else:
                self._debug_log("(* No matching condition *)")        

            nd_factor = (self._engine.get_num_states() - num_states_pre) / num_states_pre
            self._debug_log(f"(* Non-determism factor: {nd_factor} *)")

        self._append_history(event, self._engine.get_curr_states(), list(map(lambda i: f"{i[0]}?{i[1]}" ,self._engine.get_buffer_items())))
        return out
        
         


    def process_check(self):
        out = None
        if (self._onChain):
            logs = None
            #try:
            logs = self._engine.process_check()
            self._debug_log(logs[0].args.debug)
            out = logs[0].args.messageOut
            out = None if out == "None" else out
            #except Exception:
            #    pass
            #return  out
        else:
            #out = ""

            try:
                actor, message = self._engine._buffer_find_usable_message()
                out = self._engine.rule_receive_buffered(actor, message)
            except Exception:
                pass
        
        if out:
            self._append_history(out, self._engine.get_curr_states(), list(map(lambda i: f"{i[0]}?{i[1]}" ,self._engine.get_buffer_items())))
        return out


from enforcer import *
from bpmn_parser.models import *


from prompt_toolkit import prompt

class Model:

    def __init__(self):
        self._store = {}

    def add_object(self, name, obj):
        self._store[name] = obj

    def get_object(self, name):
        return self._store.get(name, None)


class UI:

    PROMPT_ENFORCER = "+> "
    PROMPT_CLI = ">> "


    def __init__(self, *args, **kwargs):
        self._registry = {
            "init"  : self.cmd_init,
            "load"  : self.cmd_load,
            "start" : self.cmd_start,
            "debug" : self.cmd_debug,
            "help"  : self.cmd_help,
            "dump"  : self.cmd_dump,
            "exit"  : self.cmd_quit,
            "quit"  : self.cmd_quit,
            "stats" : self.cmd_stats,
            "history" : self.cmd_history
        }
        self._model = Model()
        self._enforcer = None
        self._debug = True
        self._stats = []

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

    def prompt(self):
        userin = None
        if self._enforcer:
            userin = prompt(self.PROMPT_ENFORCER)
        else:
            userin = prompt(self.PROMPT_CLI)

        return userin


    def consume(self, userin):
        #self._debug_log(f"(* Consume user input: '{userin}' *)")
        if not self._enforcer or userin[0] == "/":
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
            handler(*cmd_args)
        else:
            print(f"ERROR: Command not recognized: {cmd} {' ' .join(cmd_args)}")


    def _consume_events(self, event_stream : str): #userin : str):

        assert self._enforcer is not None


        iscan = nfa.InputScanner(event_stream)

        while not iscan.eof:        
            event = iscan.scan_input()
            self._debug_log(f"\n** Process input: {event} ... **")
            out = self._enforcer.process_input(event)
            self._stats = self._enforcer._engine.stats
        
            if out:
                self._debug_log(f"\nOutput message: {out}\n")
            self._debug_log(f"** Process completed. **\n")
            
            self._debug_log("\n** Checking for usable messages in buffer ...")
            while True:
                out1 = self._enforcer.process_check()
                if out1:
                    self._debug_log(f"\nOutput message: {out1}\n")
                else:
                    break            
            self._debug_log("** Checking completed. **\n")

        if self._enforcer.ended():
            self._debug_log("(* Ended *)")
            #print("\n")
            #self.__print_stats()       
            #self._enforcer = None


    def cmd_init(self, *args, **kwargs):

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

        if len(args) != 0 and args[0] == "-clean":
            Choreography.objects.all().delete()

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

    def cmd_stats(self, *args, **kwargs):
        if self._enforcer is None:
            print("You must start the enforcer, before getting statistics")
            return
        if not self._enforcer._onChain:
            print("Statistics for off-chain Engine are not available.")
            return
        self.__print_stats()
        """if (args[0] == "-save"):
            with open(f'test_ganache.csv', 'a', encoding="utf-8") as f:
                f.write(tabulate(self._stats, headers=["Transaction", "Contract Address", "Gas Used", "Cost (Eth)", "Execution Time (s)", ""],tablefmt="tsv"))
                f.write("\n")"""

    def cmd_history(self, *args, **kwargs):
        if self._enforcer is None:
            print("You must start the enforcer, before getting statistics")
            return
        for h in self._enforcer.history:
            for key, value in h.items():
                print(f"{key} : {value}")
            print("\n")
        

    def cmd_debug(self, *args, **kwargs):

        status = "on"
        if len(args) > 0:
            status = args[0]

        if status not in [ "on", "off" ]:
            raise Exception(f"Status not recognized: {status}")

        print(f"Set debug mode : {status}")

        self._debug = (status == "on")
        if self._enforcer:
            self._enforcer.set_debug(self._debug)


    def cmd_load(self, name, *args, **kwargs):
        c : Choreography = Choreography.objects.get(name=name)
        self._model.add_object("choreography", c)


    def cmd_start(self, *args, **kwargs):

        c : Choreography = self._model.get_object("choreography")

        if len(args) > 0:
            c = Choreography.objects.get(name=args[0])

        if not c:
            raise Exception("You must load a choreography or start a choreography")

        if not os.path.exists("log.txt"):
            with open(f'log.txt', 'w', encoding="utf-8") as f:
                f.write("Run;Blockchain;Time;Transaction;Contract Address;Gas Used;Cost;Execution Time\n")

        nfa : nfa.NFA = c.to_nfa()
        self._enforcer = Enforcer(nfa)
        self._stats = self._enforcer._engine.stats

        if self._enforcer._onChain:
            self._debug_log(f"\nGas price:  {self._enforcer._engine.w3.eth.gas_price} Wei")


        if self._enforcer.ended():
            self._debug_log("(* Ended *)")
            self._enforcer = None
        

    def cmd_quit(self, *args, **kwargs):
        self._enforcer = None
        print(f"Good bye")


    def cmd_help(self, *args, **kwargs):
        print("Available commands: ")
        print(", ".join(self._registry.keys()))


    def cmd_dump(self, *args, **kwargs):
        if self._enforcer is None:
            print("You must start the enforcer, before dumping the state")
            return

        if len(args) == 0:
            print("Please specify an argument: dump <curr_states|states|transitions|buffer>")
        else:
            if args[0] == "curr_states":    
                print("\nCurrent states: \n")
                for s in self._enforcer.engine.get_curr_states():
                    label = str(s)
                    if self._enforcer.engine.is_state_initial(s):
                        label = f"{label} : i"
                    if self._enforcer.engine.is_state_final(s):
                        label = f"{label} : f"
                    print(label)
                

            elif args[0] == "transitions":
                print("\nTransitions (*=enabled): \n")
                for t in self._enforcer.engine.get_transitions():

                    t_repr = str(t)
                    if self._enforcer.engine.is_state_current(t.source):
                        t_repr = f" * {t_repr}"
                    else:
                        t_repr = f"   {t_repr}"

                    print(t_repr)

            elif args[0] == "states":
                print("\nStates (*=current, i=initial, f=final) : \n")
                for s in self._enforcer.engine.get_all_states():
                    label = str(s)

                    if self._enforcer.engine.is_state_initial(s):
                        label = f"{label} : i"

                    if self._enforcer.engine.is_state_final(s):
                        label = f"{label} : f"

                    if self._enforcer.engine.is_state_current(s):
                        label = f" * {label}"
                    else:
                        label = f"   {label}"

                    print(label)


            elif args[0] == "buffer":
                print("\nBuffer: \n")
                for actor,message in self._enforcer.engine.get_buffer_items():
                    msg = f"{actor}?{message}"

                    print(msg)

    def __enter__(self):
        return self


    def __exit__(self, *args, **kwargs):
        self.cmd_quit()


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

