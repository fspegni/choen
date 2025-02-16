from django.db import models
#from django.utils.translation import ugettext as _
from django.utils.translation import gettext as _
from django.utils import timezone
from eth_account import Account
from web3 import Web3
import re
from picklefield.fields import PickledObjectField
from django.core.exceptions import ValidationError
from bpmn_parser.models import Choreography
from django.db import transaction

from datetime import datetime
from generator import SmartContractGenerator
import uuid
import nfa
import rei
import json
import time

class Configuration(models.Model):

    label = models.CharField(max_length=100, null=True, blank=False, verbose_name=_("label"))
    url = models.CharField(max_length=1000, help_text=_("the RPC URL of the desired blockchain (see https://www.alchemy.com/chain-connect)"), verbose_name=_("url"))
    chain_id = models.CharField(max_length=50, help_text=_("this is a configuration of the chosen blockchain (see https://www.alchemy.com/chain-connect)"), verbose_name=_("chain id"))
    address = models.CharField(max_length=50, help_text=_("this is your wallet address; you can use Metamask or other tools to create one"), verbose_name=_("address"))
    private_key = models.CharField(max_length=500, help_text=_("this is supposed to be a secret; after saving the configuration, it will be hidden"), verbose_name=_("private key"))


    class Meta:
        verbose_name = _("configuration")
        verbose_name_plural = _("configurations")


    def __str__(self):
        short_url = self.url if len(self.url) < 20 else self.url[:20] + "..."
        return self.label or short_url

    def get_w3(self):
        print(f"\nConnecting to {self.url} ...")
        return Web3(Web3.HTTPProvider(self.url, request_kwargs={'timeout': 300}))

class RunningInstance(models.Model):

#    class EngineType(models.IntegerChoices):
#        OFF_CHAIN = 0
#        ON_CHAIN = 1

#    engine_type = models.IntegerField(choices=EngineType.choices, default=EngineType.OFF_CHAIN, help_text=_("the on-chain engine uses the distributed ledger, while the off-chain engine uses only local data structures (mostly for testing purposes)"))

    blockchain_configuration = models.ForeignKey(Configuration, null=True, blank=True, on_delete=models.SET_NULL, verbose_name=_("configuration"))

    label = models.CharField(max_length=500, null=True, blank=True)
    choreography = models.ForeignKey(Choreography, null=False, blank=False, on_delete=models.DO_NOTHING)
    running = models.BooleanField(default=False)
#    enforcer = PickledObjectField(blank=True, null=True) 

    # off-chain engine fields
    execution_started = models.DateTimeField(null=True, blank=True, help_text=_("The time when the instance was started, if it was ever executed"))
    execution_ended = models.DateTimeField(null=True, blank=True, help_text=_("The time when the instance was started, if it was ever executed"))

    #input_events = models.TextField(null=True, blank=True)
    #output_events = models.TextField(null=True, blank=True)
    input_events = models.JSONField(default=[], verbose_name=_("input events"))
    output_events = models.JSONField(default=[], verbose_name=_("output events"))
    

    class Meta:
        verbose_name = _("running instance")
        verbose_name_plural = _("running instances")

    @property
    def engine(self):
        e_on = getattr(self, "engineonchain", None)
        e_off = getattr(self, "engineoffchain", None)

        return e_on or e_off

    @property
    def enforcer(self):
##        if not self._enforcer:
##            print("Setting an enforcer ...")
##            self._set_enforcer()
##
        return self._enforcer

    def set_enforcer(self, enforcer):

        if self.execution_ended:
            raise Exception("Setting an enforcer for running instances that already ended is not supported")

        self._enforcer = enforcer
        if not self.running:
            self.running = True

        if not self.execution_started:
            enforcer.engine.get_execution_started()
#            self.execution_started = datetime.now() # FS this is true when a new enforcer has been deployed, it may be not true in case of an enforcer attached to a running smart contract

    @property
##    def configuration(self):
##        # TODO rename field: blockchain_configuration -> configuration
##        return self.blockchain_configuration
##
    @property
    def _running(self):
        return self.running

    @property
    def buffer(self):
        return self._enforcer.buffer if self._enforcer else None

    @property
    def rei(self):
        if not self._rei and self.choreography:
            self._rei : rei.REI = self.choreography.to_rei()
       
        return self._rei

    @property
    def nfa(self):
        return self._enforcer.engine.nfa if self._enforcer else None

    @property
    def enforcer_states(self):
        return self._enforcer.engine.curr_states if self._enforcer else None

    @property
    def enforcer_buffer(self):
        return self._enforcer.engine.get_buffer_items() if self._enforcer else None


    def __str__(self):
        #engine_type = "on-chain" if self.engine_type == self.EngineType.ON_CHAIN else "off-chain"
        engine_type = "on-chain" if self.blockchain_configuration is not None else "off-chain" 
        if self.label:
            return f"{self.label}/{self.pk} ({engine_type})"
        else:
            return f"{self.pk} ({engine_type})"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._enforcer = None
        self._rei = None

####    def _set_enforcer(self):
####        from enforcer import Enforcer
####
####        if not self.choreography:
####            raise Exception("Cannot set enforcer if a choreography is not attached to the current running instance")
####
####        automaton = self.choreography.to_nfa()
####        #if self.engine_type == self.EngineType.OFF_CHAIN:
####        if self.blockchain_configuration is None:
####            #engine = EngineOffChain(automaton)    
####            engine = EngineOffChain.create_engine(automaton)
####        else:
####
####            def handle_transactions(tx_hash, tx_receipt):
####
####                #breakpoint()
####        
####                t = Transaction()
####                t.tx_hash = tx_hash.hex()
####                t.block_hash = tx_receipt["blockHash"].hex()  
####                t.running_instance = self
####                t.initiator_address = tx_receipt["from"]
####                t.gas_used = tx_receipt["gasUsed"]
####                t.contract_address = tx_receipt["contractAddress"]
####                t.block_number = tx_receipt["blockNumber"]
####                t.save()
####       
####            #breakpoint()
#####            engine = EngineOnChain(automaton, self.blockchain_configuration.url, int(self.blockchain_configuration.chain_id), self.blockchain_configuration.address, self.blockchain_configuration.private_key, handle_transactions)
####            engine = EngineOnChain.create_engine(automaton, self.blockchain_configuration, handle_transactions)
####
####            c_nfa = Contract.objects.filter(running_instance=self, label="nfa")
####            c_enforcer = Contract.objects.filter(running_instance=self, label="enforcer")
####
####            breakpoint()
####
####            if len(c_nfa) > 0 and len(c_enforcer) > 0:
####                engine.load_smart_contracts(c_nfa[0].contract_address, c_nfa[0].abi, c_enforcer[0].contract_address, c_enforcer[0].abi)
####            else:
####                engine.deploy_smart_contracts()    
####                c_nfa = Contract.objects.create(label="nfa", running_instance=self, contract_address=engine.nfa_address, abi=engine.nfa_abi, bytecode=engine.nfa_bytecode)           
####                c_enforcer = Contract.objects.create(label="enforcer", running_instance=self, contract_address=engine.enforcer_address, abi=engine.enforcer_abi, bytecode=engine.enforcer_bytecode)           
####                engine.contract_nfa = c_nfa
####                engine.contract_enforcer = c_nfa
####                engine.save()
####
####        self._enforcer = Enforcer(engine)
####
##
## FS try to make this DEPRECATED ; TODO finish implementation/testing
##
##    def save(self, *args, **kwargs):
##
##
##        if self.engine_type == self.EngineType.ON_CHAIN and not self.blockchain_configuration:
##            raise ValueError("On-chain engine require a valid configuration")
##
##        if self.engine_type == self.EngineType.ON_CHAIN and self._enforcer is not None:
##
##            print(f"WARNING: ON_CHAIN engine type detected; not saved on database (on save)...")
##            old_engine = self.enforcer.engine
##            #self.enforcer.engine = None # FS no setter -> exception
##            self.enforcer.set_engine(None)
##            super().save(*args, **kwargs)
##            #self.enforcer.engine = old_engine # FS no setter -> exception
##            self.enforcer.set_engine(old_engine)
##        else:
##            super().save(*args, **kwargs)

    def append_input(self, new_input):
##        if not self.input_events:
##            self.input_events = new_input.strip()
##        else:
##            self.input_events = self.input_events + " " + new_input.strip()
        if not self.input_events:
            self.input_events = []

        #breakpoint()
        self.input_events.extend(re.split(r'[ ]+', new_input.strip()))
        self.save()

    def append_output(self, new_output):
##        if not self.output_events:
##            self.output_events = new_output.strip()
##        else:
##            self.output_events = self.output_events + " " + new_output.strip()
        if not self.output_events:
            self.output_events = []

        self.output_events.extend(re.split(r'[ ]+', new_output.strip()))
        self.save()

##    def attach(self, enforcer_contract_address):
##
##        raise Exception("TODO")
##
##        breakpoint()
##
##        if self.execution_ended:
##            raise Exception("Cannot attach the running instance to a contract: it has already been executed")
##        self.running = True
##
##        # 1. ensure the smart contract of the enforcer does not exist in the db
##        c_enforcer = Contract.objects.filter(contract_address=enforcer_contract_address).first()
##        if c_enforcer:
##            raise Exception(f"The smart contract ({c_enforcer}) already exists in the database. Associated running instance: {c_enforcer.running_instance}")
##
##        # 2. prepare a new proxy to the smart contract for the enforcer and link it to the
##        #    current working instance but do not save it (the running instance is not saved 
##        #    yet) 
##        c_enforcer = Contract()
##        c_enforcer.label = "enforcer"
##        c_enforcer.contract_address = enforcer_contract_address
##        c_enforcer.running_instance = self
##
##        # 3. fetch the nfa contract address using the enforcer smart contract already deployed
##        #    on the blockchain
##        nfa_contract_address = self.w3.eth.contract(
##                    address = enforcer_address,
##                    abi = self.nfa_abi
##                ).functions.nfaAddress().call()
##
##        # 4. ensure a smart contract for the nfa does not already exist in the database
##        c_nfa = Contract.objects.filter(contract_address=nfa_contract_address).first()
##        if c_nfa:
##            raise Exception(f"The smart contract ({c_nfa}) already exists in the database. Associated running instance: {c_enforcer.running_instance}")
##
##        # 5. create a proxy for the smart contract running the nfa linked to the enforcer
##        #    smart contract
##        c_nfa = Contract()
##        c_nfa.label = "nfa"
##        c_nfa.contract_address = nfa_contract_address
##        c_nfa.running_instance = self
##
##        # 6. save the current running instance (self) and the related smart contracts linked 
##        #    to it
##
##        with transaction.atomic():
##            self.save()
##            c_enforcer.save()
##            c_nfa.save()
##
##
##    def start(self):
##
##        if self.execution_ended:
##            raise Exception("Cannot start the running instance: it has already been executed")
##        self.running = True
##        self.execution_started = timezone.now()
##
##        self.save() # FS it was in the if-else branches, it has been here (refactoring)
##
##        #breakpoint()
##
#####        if self.engine_type == self.EngineType.ON_CHAIN and self._enforcer:
#####    
#####            print(f"WARNING: ON_CHAIN engine type detected; not saved on database (on start)...")
#####            old_engine = self.enforcer.engine
#####            #self.enforcer.engine = None
#####            self.enforcer.set_engine(None)
#####            #self.save()
#####            #self.enforcer.engine = old_engine
#####            self.enforcer.set_engine(old_engine)
#####        #else:
#####        #    self.save()
#####
##

    def stop(self):
        if not self.running:
            raise Exception("Cannot stop the running instance: it has not been started")
    
        if self.execution_ended:
            raise Exception("Cannot stop the running instance: its execution has been stopped")

        self.execution_ended = timezone.now()
        self.running = False
        self.save()


class Engine:

##    def __init__(self, nfa : nfa.NFA):
##
##        assert nfa is not None, f"Expected not-null nfa to build an enforcer engine"
##
##        self._debug : bool = True
##        self._nfa = nfa
##        self._history = []
##
    @property
    def nfa(self):
#        return self._nfa
        raise Exception("This is an abstract method, you should implement it")

    @property
    def history(self):
#        return self._history
        raise Exception("This is an abstract method, you should implement it")

##    def set_debug(self, debug: bool):
##        self._debug = debug
##
##    # DEBUG LOG
    def _debug_log(self, text):
#        if self._debug:
        print(text)

    def ended(self):
        raise Exception("This is an abstract method, you should implement it")

    def get_execution_started(self):
        return None

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


class EngineOffChain(Engine,models.Model):

    running_instance = models.OneToOneField(RunningInstance, null=True, blank=True, on_delete=models.SET_NULL, verbose_name="running instance")
    curr_states = models.JSONField(default=[], verbose_name=_("current states"))
    buffer = models.JSONField(default={}, verbose_name=_("buffer"))

#    def __init__(self, nfa : nfa.NFA):
    @staticmethod
    def create_engine(ri : RunningInstance): #nfa : nfa.NFA): #, blockchain_configuration : Configuration, transaction_callback = None, deploy_callback = None):

#        super().__init__(nfa)
        e = EngineOffChain()

        nfa = ri.choreography.to_nfa()

        e._nfa : nfa.NFA = nfa
        e.buffer = {}
        e.curr_states = nfa.e_closure(set([ nfa.initial.id ]))
        e._debug : bool = True
        e.stats = []
        e.running_instance = ri
        e.save()
    

    @property
    def stats(self) -> str:
        return self._stats

    def _append_history(self, event : str, curr_states : list, buffer : list):
        self._history.append({
            "event" : event, 
            "curr_states" : curr_states, 
            "buffer" : buffer}
        )

    def process_input(self, event):

        out = None
        #if self._engine.condition_rule_send(event):
        #    out = self._engine.rule_send(event)
        if self.condition_rule_send(event):
            out = self.rule_send(event)

        #elif self._engine.condition_rule_receive_now(event):
        #        out = self._engine.rule_receive_now(event)
        elif self.condition_rule_receive_now(event):
            out = self.rule_receive_now(event)

        #elif self._engine.condition_rule_receive_delayed(event):
                # TODO add check that the message may actually be consumed afterwards;
                # without this check, it does not make sense to implement the rule "Cannot receive" 
        #    out = self._engine.rule_receive_delayed(event)
        elif self.condition_rule_receive_delayed(event):
            out = self.rule_receive_delayed(event)
        else:
            self._debug_log("(* No matching condition *)")        

        self._append_history(out, self.get_curr_states(), list(map(lambda i: f"{i[0]}?{i[1]}" ,self.get_buffer_items())))

        return out


    def process_check(self):
        out = None
        try:
            #actor, message = self._engine._buffer_find_usable_message()
            actor, message = self._buffer_find_usable_message()
            #out = self._engine.rule_receive_buffered(actor, message)
            out = self.rule_receive_buffered(actor, message)
        except Exception:
            pass

        self._append_history(out, self.get_curr_states(), list(map(lambda i: f"{i[0]}?{i[1]}" ,self.get_buffer_items())))

        return out


    @property
    def buffer(self) -> dict:
        return self._buffer

    @property
    def curr_states(self) -> str:
        return self._curr_states

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
#        print("in _buffer_find_usable_message...")

#        print(f"Buffer: {self._buffer}")
        for actor, actor_buffer in self._buffer.items():
#            print(f"Actor: {actor} - Actor buffer: {actor_buffer}")
            for message, counter in actor_buffer.items():
#                print(f"Message: {message} - Counter: {counter}")
                if counter > 0:
                    event = f"{actor}?{message}"
                    for s in self._curr_states:
                        if self._nfa.transitions_from(s, event):
                            found = (actor, message)
                            return found
        
        raise Enforcer.NoMessageFound("No usable message found")

    
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

        for actor,actor_buffer in self._buffer.items():
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

class Contract(models.Model):

    contract_address =models.CharField(max_length=100, null=True, blank=False, verbose_name=_("contract address"))
    #running_instance = models.ForeignKey(RunningInstance, null=True, blank=False, on_delete=models.SET_NULL, verbose_name=_("running instance"))
    label = models.CharField(max_length=100, verbose_name=_("label"))
    abi = models.JSONField(null=True, blank=False, verbose_name=_("abi"))
    bytecode = models.TextField(null=True, blank=False, verbose_name=_("bytecode"))
   

    class Meta:
        verbose_name = _("contract")
        verbose_name_plural = _("contracts")
        unique_together = (("contract_address",),)# ("label", "running_instance"))

    def __str__(self):
        return f"{self.contract_address}/{self.label}/{self.id}"



class EngineOnChain(Engine,models.Model):

    running_instance = models.OneToOneField(RunningInstance, null=True, blank=True, on_delete=models.SET_NULL, verbose_name="running instance")
    blockchain_configuration = models.ForeignKey(Configuration, null=True, blank=True, on_delete=models.SET_NULL, verbose_name=_("configuration"))

    contract_nfa = models.OneToOneField(Contract, null=True, on_delete=models.SET_NULL, verbose_name=_("contract nfa"), related_name="nfa_engine")
    contract_enforcer = models.OneToOneField(Contract, null=True, on_delete=models.SET_NULL, verbose_name=_("contract enforcer"), related_name="enforcer_engine")

    stats = models.JSONField(default = [])

#    def __init__(self, nfa : nfa.NFA, chain_url : str, chain_id : int, wallet_address : str, private_key : str, transaction_callback = None, deploy_callback = None):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._transaction_callback = None
        self._deploy_callback = None

        self._debug : bool = True
        self._runID = uuid.uuid4()


    @staticmethod
    def create_engine(ri : RunningInstance, transaction_callback = None, deploy_callback = None): #nfa : nfa.NFA, blockchain_configuration : Configuration, transaction_callback = None, deploy_callback = None):

        nfa = ri.choreography.to_nfa()
        blockchain_configuration = ri.blockchain_configuration
#        super().__init__(nfa)

##        assert wallet_address is not None, "You must configure your wallet address before continuing"
##        assert private_key is not None, "You must configure your wallet private key before continuing"
##        assert chain_url is not None, "You must configure your blockchain URL before continuing"
##        assert chain_id is not None, "You must configure your blockchain chain ID before continuing"
##
##        self._chain_url = chain_url 
##        self._chain_id = chain_id
##        self._wallet_address = wallet_address
##        self._private_key = private_key
##

        e = EngineOnChain()
        e._nfa = nfa
        e.blockchain_configuration = blockchain_configuration
        e._w3 : Web3 = blockchain_configuration.get_w3()
        e._debug_log("Connected.")

        # test network connection, by retrieving the network_id
        network_id = e._w3.net.version
        e._debug_log(f"Network ID: {network_id}")
        
        # test account
        account = Account.from_key(blockchain_configuration.private_key)
        balance = e._w3.eth.get_balance(account.address) 
        print(f"Account: {account.address}. Balance: {e.w3.from_wei(balance, 'ether')} ETH")
        #e._stats = []

        #breakpoint()
        e._transaction_callback = transaction_callback
        e._deploy_callback = deploy_callback

        e.running_instance = ri
        e.save()

        return e

##        self._nfa_address = None
##        self._nfa_abi = None
##        self._nfa_bytecode = None
##
##        self._enforcer_address = None
##        self._enforcer_abi = None
##        self._enforcer_bytecode = None
##
    def load_smart_contracts(self, nfa_address, nfa_abi, enforcer_address, enforcer_abi):

        self._nfa_abi = nfa_abi
        self._nfa_address = nfa_address
        self._enforcer_abi = enforcer_abi
        self._enforcer_address = enforcer_address


    def deploy_smart_contracts(self):

        if not self._nfa:
            raise Exception("No NFA has been set for this purpose")

        scg: SmartContractGenerator = SmartContractGenerator(self._nfa)
        compiled_sol = scg.createSmartContract().compile(self._debug)
        
        self._nfa_abi, self._nfa_bytecode = self.__get_abi_and_bytecode(compiled_sol, "NFA")
        self._enforcer_abi, self._enforcer_bytecode = self.__get_abi_and_bytecode(compiled_sol, "Enforcer")

        self._nfa_address = self.deployContractNFA(self._nfa_abi, self._nfa_bytecode)
        self._enforcer_address = self.deployContractEnforcer(self._enforcer_abi, self._enforcer_bytecode, self._nfa_address)


    def attach_smart_contracts(self, sc_enforcer_address):

        #if not self._nfa:
        #    raise Exception("No NFA has been set for this purpose")

        # compile the smart contracts to get the abi and bytecode for each
        #scg: SmartContractGenerator = SmartContractGenerator(self._nfa)
        #compiled_sol = scg.createSmartContract().compile(self._debug)
        
        #self._nfa_abi, self._nfa_bytecode = self.__get_abi_and_bytecode(compiled_sol, "NFA")
        #self._enforcer_abi, self._enforcer_bytecode = self.__get_abi_and_bytecode(compiled_sol, "Enforcer")
        self._nfa_abi = self.contract_nfa.abi
        self._nfa_bytecode = self.contract_nfa.bytecode
        self._enforcer_abi = self.contract_enforcer.abi
        self._enforcer_bytecode = self.contract_enforcer.bytecode

        # query the enforcer smart contract to get the address of the nfa smart contract
        # (from blockchain)    

        self._enforcer_address = sc_enforcer_address

        print(f"Fetching NFA contract address from enforcer smart contract ...")
        self._nfa_address = self.w3.eth.contract(
                address = sc_enforcer_address,
                abi = self.enforcer_abi
            ).functions.getNfaAddress().call()


    @property
    def w3(self) -> Web3:
        w3 = getattr(self, "_w3", None)
        if not w3:
            self._w3 = self.blockchain_configuration.get_w3()

        return self._w3
    
    @property
    def chain_id(self) -> int:
        return self.blockchain_configuration.chain_id if self.blockchain_configuration else None

    @property
    def address(self) -> str:
        return self.blockchain_configuration.address if self.blockchain_configuration else None

    @property
    def private_key(self) -> str:
        return self.blockchain_configuration.private_key if self.blockchain_configuration else None
    
    #@property
    #def stats(self) -> str:
    #    return self._stats

    @property
    def nfa_abi(self):
        return self.contract_nfa.abi if self.contract_nfa else None
    
    @property
    def nfa_bytecode(self) -> str:
        return self.contract_nfa.bytecode if self.contract_nfa else None

    @property 
    def nfa_address(self) -> str:
        return self.contract_nfa.contract_address if self.contract_nfa else None

    @property
    def enforcer_abi(self):
        return self.contract_enforcer.abi if self.contract_enforcer else None
    
    @property
    def enforcer_bytecode(self) -> str:
        return self.contract_enforcer.bytecode if self.contract_enforcer else None
    
    @property
    def enforcer_address(self) -> str:
        return self.contract_enforcer.contract_address if self.contract_enforcer else None

    def __get_abi_and_bytecode(self, compiled_sol, contract : str):
        #get bytecode
        bytecode = compiled_sol["contracts"]["smart_contract.sol"][contract]["evm"]["bytecode"]["object"]
        
        #get abi
        abi = json.loads(compiled_sol["contracts"]["smart_contract.sol"][contract]["metadata"])["output"]["abi"]

        return abi, bytecode

    def __log(self, contractAddress, gasUsed, cost, executionTime, type = None):
        with open(f'log.txt', 'a', encoding="utf-8") as f:
                f.write(f"{self._runID};{self.chain_id};{datetime.now()};{type};{contractAddress};{gasUsed};{cost};{executionTime}\n")
                #f.write(tabulate(self._stats, headers=["Transaction", "Contract Address", "Gas Used", "Cost (Eth)", "Execution Time (s)", ""],tablefmt="tsv"))
                #f.write("\n")
    
    def __add_statistics(self, contractAddress, gasUsed, cost, executionTime, type = None):
        #breakpoint()
        self.stats.append([type, contractAddress, gasUsed, float(cost), executionTime])
    
    def __sendTransaction(self, transaction):
        # Sign the transaction
        sign_transaction = self.w3.eth.account.sign_transaction(transaction, private_key = self.private_key)
        
        # Send the transaction
        #tx_hash = self.w3.eth.send_raw_transaction(sign_transaction.rawTransaction)
        tx_hash = self.w3.eth.send_raw_transaction(sign_transaction.raw_transaction)
        
        print(f"Transaction hash: {tx_hash.hex()}. Wait for validation ...")
        # Wait for the transaction to be mined, and get the transaction receipt
        tx_receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=600)
        print(f"Transaction validated. Receipt: {tx_receipt}")

        #breakpoint()
        if self._transaction_callback:
            self._transaction_callback(tx_hash, tx_receipt)

        return tx_receipt

    def __deployContract(self, contract_name : str, abi, bytecode, address = None):
        #create the contract
        contract = self.w3.eth.contract(abi=abi, bytecode=bytecode)

        #nonce =  self.w3.eth.get_transaction_count(self.address)
        nonce = self.w3.eth.get_transaction_count(self.address, "pending") # FS added pending, trying to solve the "nonce too low" problem

        start_time = time.time()
        # build transaction
        if (address == None):
#            transaction = contract.constructor().buildTransaction(
            transaction = contract.constructor().build_transaction(
            {
                "chainId": self.w3.eth.chain_id, #self.chain_id,
                "gasPrice": self.w3.eth.gas_price,
                "from": self.address,
                "nonce": nonce,
            }
        )
        else:
#            transaction = contract.constructor(address).buildTransaction(
            transaction = contract.constructor(address).build_transaction(
            {
                "chainId": self.w3.eth.chain_id, #self.chain_id,
                "gasPrice": self.w3.eth.gas_price,
                "from": self.address,
                "nonce": nonce,
            }
        )
        build_time = time.time() - start_time
        self._debug_log(f"\nDeploying contract {contract_name} ...")
        tx_receipt = self.__sendTransaction(transaction)
        execution_time = time.time() - start_time
        self.__add_statistics(tx_receipt.contractAddress ,tx_receipt.gasUsed, round(self.w3.from_wei(tx_receipt.gasUsed * self._w3.eth.gas_price, 'ether'),2), round(execution_time,3), f"Contract Creation")
        self.__log(tx_receipt.contractAddress ,tx_receipt.gasUsed, round(self.w3.from_wei(tx_receipt.gasUsed * self._w3.eth.gas_price, 'ether'),2), round(execution_time,3),f"Contract Creation")
        self._debug_log(f"Done! Contract deployed to {tx_receipt.contractAddress}\n")
        return tx_receipt.contractAddress


    def deployContractNFA(self, abi, bytecode):
        return self.__deployContract("NFA", abi, bytecode)
    
    def deployContractEnforcer(self, abi, bytecode, nfa_address : str):
        return self.__deployContract("Enforcer", abi, bytecode, nfa_address)


    @property
    def buffer(self):
        return self.get_buffer_items()

    # INTERFACE methods

    def ended(self):
        return self.w3.eth.contract(
                address = self.nfa_address,
                abi = self.nfa_abi
#            ).functions.isFinal().call()
            ).functions.isEnded().call()

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
        return self._nfa.transitions # TODO FS

    def is_state_final(self, s):
#        return self._nfa.is_final(s)
        return self.w3.eth.contract(
                address = self.nfa_address,
                abi = self.nfa_abi
            ).functions.isFinal(s).call()

    def is_state_initial(self, s):  
#        return self._nfa.is_initial(s)
        return self.w3.eth.contract(
                address = self.nfa_address,
                abi = self.nfa_abi
            ).functions.isInitial(s).call()

    def is_state_current(self, s):
        if isinstance(s, nfa.State):
            s = s.id
#
#        curr_states = self.get_curr_states()
#        return s in curr_states
        return self.w3.eth.contract(
                address = self.nfa_address,
                abi = self.nfa_abi
            ).functions.isCurrent(s).call() 

    def get_buffer_items(self):
        #breakpoint()
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
        nonce = self.w3.eth.get_transaction_count(self.address, "pending") # FS added 'pending' ot solve the nonce too low problem
        start_time = time.time()
#        transaction = enforcer.functions.process_input(event).buildTransaction({
        transaction = enforcer.functions.process_input(event).build_transaction({
                        "chainId": self.w3.eth.chain_id, #self.chain_id,
                        "from": self.address,
                        "gasPrice": self.w3.eth.gas_price,
                        "nonce": nonce
                    })
        build_time = time.time() - start_time

        self._debug_log(f"\nProcess input {event} ...")
        tx_receipt = self.__sendTransaction(transaction)
        execution_time = time.time() - start_time
        self.__add_statistics(tx_receipt.contractAddress ,tx_receipt.gasUsed, round(self.w3.from_wei(tx_receipt.gasUsed * self._w3.eth.gas_price, 'ether'),2), round(execution_time,3), f"Process input: {event}")
        self.__log(tx_receipt.contractAddress ,tx_receipt.gasUsed, round(self.w3.from_wei(tx_receipt.gasUsed * self._w3.eth.gas_price, 'ether'),2), round(execution_time,3), f"Process input: {event}")
#        return enforcer.events.outputEvent().processReceipt(tx_receipt)
        logs = enforcer.events.outputEvent().process_receipt(tx_receipt)

        self._debug_log(logs[0].args.debug)
        out = logs[0].args.messageOut
        out = None if out == "None" else out
        return out
 

    def process_check(self):
        enforcer = self.w3.eth.contract(
                address = self.enforcer_address,
                abi = self.enforcer_abi
            )
        nonce = self.w3.eth.get_transaction_count(self.address, "pending") # FS added 'pending', trying to solve the nonce-too-low problem
        start_time = time.time()
#        transaction = enforcer.functions.process_check().buildTransaction({
        transaction = enforcer.functions.process_check().build_transaction({
                        "chainId": self.w3.eth.chain_id, #self.chain_id,
                        "from": self.address,
                        "gasPrice": self.w3.eth.gas_price,
                        "nonce": nonce
                    })
        build_time = time.time() - start_time

        self._debug_log(f"\nProcess check ...")
        tx_receipt = self.__sendTransaction(transaction)
        execution_time = time.time() - start_time
        self.__add_statistics(tx_receipt.contractAddress ,tx_receipt.gasUsed, self.w3.from_wei(tx_receipt.gasUsed * self._w3.eth.gas_price, 'ether'), round(execution_time,3), f"Process check")
        self.__log(tx_receipt.contractAddress ,tx_receipt.gasUsed, self.w3.from_wei(tx_receipt.gasUsed * self._w3.eth.gas_price, 'ether'), round(execution_time,3), f"Process check")
        receipt = enforcer.events.outputEvent().process_receipt(tx_receipt)

        self._debug_log(logs[0].args.debug)
        out = logs[0].args.messageOut
        out = None if out == "None" else out

        return out


class Transaction(models.Model):

    tx_hash = models.CharField(max_length=100, null=True, blank=False, verbose_name=_("hash"))
    block_hash = models.CharField(max_length=100, null=True, blank=False, verbose_name=_("block hash"))
    #running_instance = models.ForeignKey(RunningInstance, null=True, blank=False, on_delete=models.SET_NULL, verbose_name=_("running instance"))

    as_of = models.DateTimeField(null=True, blank=False, help_text=_("The time when the transaction was recorded"))
    gas_used = models.IntegerField(null=True, help_text=_("gas used"))
    contract_address =models.CharField(max_length=100, null=True, blank=False, verbose_name=_("contract address"))
    initiator_address =models.CharField(max_length=100, null=True, blank=False, verbose_name=_("initiator address"))
    block_number =models.IntegerField(null=True, blank=False, verbose_name=_("block number"))

    class Meta:
        verbose_name = _("transaction")
        verbose_name_plural = _("transactions")
        unique_together = (("tx_hash",))

#    def save(self, *args, **kwargs):
#        self.as_of = timezone.now()
#        super().save(self, *args, **kwargs)
