from django.db import models
#from django.utils.translation import ugettext as _
from django.utils.translation import gettext as _
from django.utils import timezone
from eth_account import Account
from web3 import Web3, HTTPProvider
#from web3.middleware import SignAndSendRawMiddlewareBuilder
#from web3.middleware.signing import NonceManager

import re
from picklefield.fields import PickledObjectField
from django.core.exceptions import ValidationError
from bpmn_parser.models import Choreography
from django.db import transaction
from django.conf import settings

from datetime import datetime
from generator import SmartContractGenerator
import uuid
import nfa
import rei
import json
import time
import logging
import traceback
import requests
from functools import wraps


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

    def get_account(self):
        account = Account.from_key(self.private_key)
        return account

    def get_w3(self):
        print(f"\nConnecting to {self.url} ...")
        w3 = Web3(Web3.HTTPProvider(self.url, request_kwargs={'timeout': 300}))

        # NB not needed; w3 v7.5 now computes nonce automatically if you don't specify
        # Add automatic nonce management
        #w3.middleware_onion.add(NonceManager())

        # Add automatic signing + sending
        #account = self.get_account()
        #sign_and_send_mw = SignAndSendRawMiddlewareBuilder().build(account)
        #w3.middleware_onion.add(sign_and_send_mw)

        return w3

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
    def execution_started(self):
        return self.engine.get_execution_started() if self.engine else None

    @property
    def execution_ended(self):
        return self.engine.get_execution_ended() if self.engine else None

    @property
    def engine_type(self):
        e = self.engine
        return e.__class__.__name__ if e else "N/N"


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

#        if not self.execution_started and enforcer.engine:
#            self._execution_started = enforcer.engine.get_execution_started()
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
    def kb(self):
        return self._enforcer.kb if self._enforcer else None

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

        self.output_events.extend(re.split(r'[ ]+', str(new_output)))#.strip()))
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

        #self.execution_ended = timezone.now()
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
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._nfa = None
        self._log_file = None


    @property
    def log_file(self):
        return self._log_file

    def set_log_file(self, log_file):
        self._log_file = log_file
        

    @property
    def nfa(self):
        return self._nfa
#        raise Exception("This is an abstract method, you should implement it")

    def set_nfa(self, nfa):
        self._nfa = nfa

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
        #return None
        raise Exception("This is an abstract method, you should implement it")

    def get_execution_ended(self):
        #return None
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

    def get_kb(self):
        raise Exception("This is an abstract method, you should implement it")

    # RULE CONDITIONS
    def condition_rule_send_now(self, precondition, event):
        raise Exception("This is an abstract method, you should implement it")

    def condition_rule_send_delayed(self, precondition, event):
        raise Exception("This is an abstract method, you should implement it")

##    def condition_rule_send_buffered(self, precondition, event):
##        raise Exception("This is an abstract method, you should implement it")



    def condition_rule_receive_now(self, precondition, event):
        raise Exception("This is an abstract method, you should implement it")

    def condition_rule_receive_delayed(self, precondition, event):
        raise Exception("This is an abstract method, you should implement it")
 
##    def condition_rule_receive_buffered(self, precondition, event):
##        raise Exception("This is an abstract method, you should implement it")

  
    # RULE EFFECTS
    def rule_send_now(self, precondition, event, knowledge):
        raise Exception("This is an abstract method, you should implement it")
 
    def rule_send_delayed(self, precondition, event, knowledge):
        raise Exception("This is an abstract method, you should implement it")
  
    def rule_send_buffered(self, precondition, event, knowledge):
        raise Exception("This is an abstract method, you should implement it")

    def rule_receive_now(self, precondition, event, knowledge):

        raise Exception("This is an abstract method, you should implement it")

    def rule_receive_delayed(self, precondition, event, knowledge):

        raise Exception("This is an abstract method, you should implement it")

    def rule_receive_buffered(self, precondition, event, knowledge):

        raise Exception("This is an abstract method, you should implement it")



class EngineOffChain(Engine,models.Model):

    running_instance = models.OneToOneField(RunningInstance, null=True, blank=True, on_delete=models.SET_NULL, verbose_name="running instance")
    curr_states = models.JSONField(default=[], verbose_name=_("current states"))
    history = models.JSONField(default=[], verbose_name=_("current states"))
    buffer = models.JSONField(default={}, verbose_name=_("buffer"))
    kb = models.JSONField(default=[], verbose_name=_("knowledge base"))

    execution_started = models.DateTimeField(null=True, blank=True, help_text=_("The time when the instance was started, if it was ever executed"))
    execution_ended = models.DateTimeField(null=True, blank=True, help_text=_("The time when the instance was started, if it was ever executed"))

#    def __init__(self, nfa : nfa.NFA):
    @staticmethod
    def create_engine(ri : RunningInstance): #nfa : nfa.NFA): #, blockchain_configuration : Configuration, transaction_callback = None, deploy_callback = None):

#        super().__init__(nfa)
        e = EngineOffChain()

        #breakpoint()
        nfa = ri.choreography.to_nfa(optimize=True)
        #nfa.remove_epsilon_transitions()
        #nfa.remove_unreachable_states()

        e._nfa : nfa.NFA = nfa
        e.buffer = {}
        e.curr_states = list(nfa.e_closure(set([ nfa.initial.id ])))
        e._debug : bool = True
        e._stats = []
        e.running_instance = ri
        e.kb = []

        e.execution_started = timezone.now()

        e.save()

        return e
    

    @property
    def stats(self) -> str:
        return self._stats


    def get_execution_started(self):
        return self.execution_started

    def get_execution_ended(self):
        return self.execution_ended

    def _append_history(self, event : str, curr_states : list, buffer : list):
        self.history.append({
            "event" : event, 
            "curr_states" : curr_states, 
            "buffer" : buffer}
        )

    def _parse_event(self, symbol):
    
        m = re.match("^([^!?]+)([!?])([^!?]+)$", symbol)

        return m.groups() if m else (None, None, None)
    
    #def process_input(self, symbol):
    def process_input(self, precondition, event, knowledge):

        out = None
        #if self._engine.condition_rule_send(event):
        #    out = self._engine.rule_send(event)

        #(precondition, actor, action, message, knowledge) = self._parse_event(symbol)
        (actor, action, message) = self._parse_event(event)


        #event = f"{actor}{action}{message}"
        print(f"Process: {precondition or 'T'} -> {event}({knowledge or 'nil'})")

        #breakpoint()
        if self.condition_rule_send_now(precondition, event):
            out = self.rule_send_now(precondition, event, knowledge)

        elif self.condition_rule_send_delayed(precondition, event):
            out = self.rule_send_delayed(precondition, event, knowledge)

        #elif self._engine.condition_rule_receive_now(event):
        #        out = self._engine.rule_receive_now(event)
        elif self.condition_rule_receive_now(precondition, event):
            out = self.rule_receive_now(precondition, event, knowledge)

        #elif self._engine.condition_rule_receive_delayed(event):
                # TODO add check that the message may actually be consumed afterwards;
                # without this check, it does not make sense to implement the rule "Cannot receive" 
        #    out = self._engine.rule_receive_delayed(event)
        elif self.condition_rule_receive_delayed(precondition, event):

            #breakpoint()
            out = self.rule_receive_delayed(precondition, event, knowledge)
        else:
            self._debug_log("(* No matching condition *)")        

        #breakpoint()
        self._append_history(out, self.get_curr_states(), list(map(lambda i: f"{i[2]}:{i[0]}?{i[1]}({i[3]})" ,self.get_buffer_items())))

        self.save()
        return out


    def process_check(self):

        from enforcer import Enforcer

        out = None
        #breakpoint()
        try:
            #actor, message = self._engine._buffer_find_usable_message()

            precondition, event, knowledge = self.buffer_find_usable_event()
            #out = self._engine.rule_receive_buffered(actor, message)

            (actor, action, message) = self._parse_event(event) #symbol)

            #breakpoint()
            if action == "!": #message.starts_with("!"):
                out = self.rule_send_buffered(precondition, actor, message, event, knowledge)
            elif action == "?":
                out = self.rule_receive_buffered(precondition, actor, message, event, knowledge)
            else:
                raise ValueError(f"Unexpected action: {action}")
        except Enforcer.NoMessageFound: #Exception:
            pass

        #breakpoint()
        self._append_history(out, self.get_curr_states(), list(map(lambda i: f"{i[0]}{i[1]}" ,self.get_buffer_items())))


        self.save()
        return out

#
#    @property
#    def buffer(self) -> dict:
#        return self._buffer

#    @property
#    def curr_states(self) -> str:
#        return self._curr_states

    # UTILS
##
##    def _buffer_add(self, precondition, actor : str, message : str, knowledge):
##
##        # TODO what to do with precondition and knowledge?
##        actor_buffer = self.buffer.get(actor, {})
##        message_counter = actor_buffer.get(message, 0)
##        actor_buffer[message] = message_counter + 1
##        self.buffer[actor] = actor_buffer
##
##    def _buffer_remove(self, actor : str, message : str):
##
##        actor_buffer = self.buffer.get(actor, {})
##        message_counter = actor_buffer.get(message, 0)
##        assert message_counter >= 0
##
##        if message_counter <= 0:
##            raise Exception(f"No message {message} to remove for actor {actor}")
##        
##        actor_buffer[message] = message_counter - 1
##        self.buffer[actor] = actor_buffer
##

    def _buffer_add(self, precondition, actor : str, message : str, knowledge):

        if not actor in self.buffer:
            self.buffer[actor] = {}

        if not message in self.buffer[actor]:
            self.buffer[actor][message] = []

        self.buffer[actor][message].append({"precondition": precondition, "knowledge": knowledge})

    def _buffer_remove(self, precondition, actor : str, message : str, knowledge):

        if not actor in self.buffer:
            raise Exception(f"No message to remove for actor {actor}")

        if not message in self.buffer[actor]:
            raise Exception(f"No message {message} to remove for actor {actor}")

        for (idx,curr) in enumerate(self.buffer[actor][message]):
            if curr["precondition"] == precondition and curr["knowledge"] == knowledge:
                del self.buffer[actor][message][idx]
                return # successful case

        # if it reaches here, no message with precondition and knowledge was found for actor, thus raise an exception
        raise Exception(f"No message {message} to remove for actor {actor} with given precondition and knowledge")
        
    
##    def buffer_find_usable_event(self):
##        found = None
###        print("in _buffer_find_usable_message...")
##
###        print(f"Buffer: {self._buffer}")
##        for actor, actor_buffer in self.buffer.items():
###            print(f"Actor: {actor} - Actor buffer: {actor_buffer}")
##            for message, counter in actor_buffer.items():
###                print(f"Message: {message} - Counter: {counter}")
##                if counter > 0:
##                    event = f"{actor}{message}"
##                    for s in self.curr_states:
##                        if self._nfa.transitions_from(s, event):
##                            #found = (actor, message)
##                            #return found
##                            return None, event, None # TODO at the moment we do not return any precondition nor knowledge
##        
##        raise Enforcer.NoMessageFound("No usable message found")
##

    def buffer_find_usable_event(self):

        from enforcer import Enforcer

        found = None
        for actor in self.buffer:
            for message in self.buffer[actor]:
                event = f"{actor}{message}"
                for curr in self.buffer[actor][message]:
                    if not "precondition" in curr or not "knowledge" in curr: 
                        raise Exception(f"Ill-formed buffer item. Expected item with 'precondition' and 'knowledge'. Found: {curr}")

                    precondition = curr["precondition"]
                    knowledge = curr["knowledge"]
                
                    for s in self.curr_states:
                        if self._nfa.transitions_from(s, event) and self.check_sat(precondition):
                            return precondition, event, knowledge
                        
        raise Enforcer.NoMessageFound("No usable message found")

    # INTERFACE methods

    def add_knowledge(self, knowledge):
        if not knowledge:   
            return

        for p in knowledge:
            m = re.match("^(!)?([a-zA-Z0-9]+)$", p)
    
            if not m:
                raise Exception(f"Unexpected format for proposition: {p}")
    
            neg, prop = m.groups()
    
            if neg:
                try:
                    self.kb = self.kb.remove(prop)
                except ValueError:
                    # element not present, no problem
                    pass
            else:
                self.kb = list(set(self.kb + [ prop ]))
    
    def check_sat(self, formula):
        if not formula:
            # tautology
            return True
        #breakpoint()
        # at the moment assume the formula is a single proposition
        m = re.match("^(!)?([a-zA-Z0-9]+)", formula)
        if not m:
            raise Exception(f"Formula not recognized: {formula}")

        neg, prop = m.groups()

        if neg:
            return prop not in self.kb
        else:
            return prop in self.kb

    def ended(self):
        return self._nfa.is_final(self.curr_states)

    def get_all_states(self):
        return self._nfa.states

    def get_curr_states(self):
        return self.curr_states

    def get_transitions(self):
        return self._nfa.transitions

    def is_state_final(self, s):
        return self._nfa.is_final(s)

    def is_state_initial(self, s):  
        return self._nfa.is_initial(s)

    def is_state_current(self, s):
        if isinstance(s, nfa.State):
            s = s.id
        
        res = (s in self.curr_states)
        return res
##
##    def get_buffer_items(self):
##        items = []
##
##        for actor,actor_buffer in self.buffer.items():
##            for message,counter in actor_buffer.items():
##                for i in range(counter):
##                    items.append((actor, message))
##        return items

    def get_buffer_items(self):
        items = []
        for actor in self.buffer:
            for message in self.buffer[actor]:
                for curr in self.buffer[actor][message]:
                    items.append((actor, message, curr["precondition"], curr["knowledge"]))

        return items

    def get_kb(self):
        return self.kb

    # CONDITIONS below

    def condition_rule_send_now(self, precondition, event):
    
        if not self.check_sat(precondition):
            return False           

        m = re.match("^[^?!]+![^!?]+$", event) 

        if m is None:
            return False

        for curr in self.curr_states:
            enabled_transitions = self._nfa.transitions_from(curr, event)

            if len(enabled_transitions) > 0:

                self._debug_log(f"(* Condition rule send now *)") #: {precondition or 'T'} -> {event} *)")
                return True

        return False

    def condition_rule_send_delayed(self, precondition, event):    

        m = re.match("^[^!?]+\![^!?]+$", event) 
        if not m:
            return False

#        if self.check_sat(precondition):
#            return False


        # TODO restrict the loop below to only states that are reachable from current one
        for curr in self._nfa.states:
            enabled_transitions = self._nfa.transitions_from(curr, event)
            if len(enabled_transitions) > 0:
                self._debug_log(f"(* Condition rule receive delayed *)") #: {precondition or 'T'} -> {event} *)")
                return True


        #self._debug_log(f"(* Condition rule send delayed: {precondition} -> {event} *)")
        #return m is not None
        return False #True

##    def condition_rule_send_buffered(self, precondition, event):
##
##        m = re.match("^[^!?]+\![^!?]+$", event) 
##        if not m:
##            return False
##
##        if not self.check_sat(precondition):
##            return False
##
##        # TODO check (FS)
##
##        self._debug_log(f"(* Condition rule send buffered: {precondition} -> {event} *)")
##        return True
##

    def condition_rule_receive_now(self, precondition, event):

        if not self.check_sat(precondition):
            return False

        m = re.match("^[^!?]+\?[^!?]+$", event) 
        if m is None:
            return False

        for curr in self.curr_states:
            enabled_transitions = self._nfa.transitions_from(curr, event)

            if len(enabled_transitions) > 0:

                self._debug_log(f"(* Condition rule receive now *)") #: {precondition or 'T'} -> {event} *)")
                return True

        return False

    def condition_rule_receive_delayed(self, precondition, event):    
    
        m = re.match("^[^!?]+\?[^!?]+$", event) 
        if not m:
            return False
    
#        if self.check_sat(precondition):
#            return False

        # TODO restrict the loop below to only states that are reachable from current one
        for curr in self._nfa.states:
            enabled_transitions = self._nfa.transitions_from(curr, event)
            if len(enabled_transitions) > 0:
                self._debug_log(f"(* Condition rule receive delayed *)") #: {precondition or 'T'} -> {event} *)")
                return True

        return False #True
##
##    def condition_rule_receive_buffered(self, precondition, event):
##
##        m = re.match("^[^!?]+\?[^!?]+$", event) 
##        if not m:
##            return False
##
##        if not self.check_sat(precondition):
##            return False
##
##        # TODO check (FS)
##
##        self._debug_log(f"(* Condition rule receive buffered: {precondition} -> {event} *)")
##        return True
##


    # RULES below

    def rule_send_now(self, precondition, event, knowledge):
        reached = set()
        for s in self.curr_states:

            s_reached = self._nfa.read_symbol(event, s)

            if len(s_reached) == 0:
                self._debug_log(f"(* State {s} was not compatible with event {event} and has been discarded... *)")
            else:
                reached = reached.union(s_reached)
            

        self.curr_states = list(reached)

        self.add_knowledge(knowledge)
        return event

    def rule_send_delayed(self, precondition, event, knowledge):
        # TODO we should buffer the precondition and knowledge
        actor, message = event.split("!")
        self._buffer_add(precondition, actor, "!" + message, knowledge)
        return ""

    #def rule_send_buffered(self, precondition, event, knowledge):
    def rule_send_buffered(self, precondition, actor, message, event, knowledge):
        
        #_, actor, action, message, _ = self._parse_event(event)

        assert actor in self.buffer and "!" + message in self.buffer[actor]
        
        #counter = self.buffer[actor][action + message]

        #assert counter > 0

        #event = f"{actor}!{message}"
        #event = f"{actor}{action}{message}"

        reached = set()
        for s in self.curr_states:
            s_reached = self._nfa.read_symbol(event, s)

            if len(s_reached) == 0:
                self._debug_log(f"(* State {s} was not compatible with event {event} and has been discarded... *)")
            else:
                reached = reached.union(s_reached)
        
        self._buffer_remove(precondition, actor, "!" + message, knowledge)

        nd_factor = (len(reached) - len(self.curr_states)) / len(self.curr_states)
        #self._debug_log(f"(* Non-determinism factor: {nd_factor} *)")
        self.curr_states = list(reached)

        self.add_knowledge(knowledge)
        return event


    def rule_receive_now(self, precondition, event, knowledge):

        reached = set()
        for s in self.curr_states:

            s_reached = self._nfa.read_symbol(event, s)

            if len(s_reached) == 0:
                self._debug_log(f"(* State {s} was not compatible with event {event} and has been discarded... *)")
            else:
                reached = reached.union(s_reached)
            

        self.curr_states = list(reached)

        self.add_knowledge(knowledge)
        return event

#    def rule_receive_delayed(self, actor, message):
    def rule_receive_delayed(self, precondition, event, knowledge):
        # TODO we should buffer the precondition and knowledge
        actor, message = event.split("?")
        self._buffer_add(precondition, actor, "?" + message, knowledge)
        return ""

    def rule_receive_buffered(self, precondition, actor, message, event, knowledge):
        
        #_, actor, action, message, _ = self._parse_event(event)

        assert actor in self.buffer and "?" + message in self.buffer[actor]
        
        #counter = self.buffer[actor][action + message]

        #assert counter > 0

        #event = f"{actor}?{message}"
        #event = f"{actor}{action}{message}"

        reached = set()
        for s in self.curr_states:
            s_reached = self._nfa.read_symbol(event, s)

            if len(s_reached) == 0:
                self._debug_log(f"(* State {s} was not compatible with event {event} and has been discarded... *)")
            else:
                reached = reached.union(s_reached)
        
        self._buffer_remove(precondition, actor, "?" + message, knowledge)

        nd_factor = (len(reached) - len(self.curr_states)) / len(self.curr_states)
        #self._debug_log(f"(* Non-determinism factor: {nd_factor} *)")
        self.curr_states = list(reached)

        self.add_knowledge(knowledge)
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

    @property
    def running_instance(self):
        return self.enforcer_engine.running_instance if self.enforcer_engine else None

    @property
    def choreography(self):
        return self.running_instance.choreography if self.running_instance else None

    @property
    def bytecode_size(self):
        return len(self.bytecode) if self.bytecode else 0

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

    @property
    def contract_nfa_size(self):
        return self.contract_nfa.bytecode_size if self.contract_nfa else 0

    @property
    def contract_enforcer_size(self):
        return self.contract_enforcer.bytecode_size if self.contract_enforcer else 0

    @property
    def contracts_size(self):
        return self.contract_nfa_size + self.contract_enforcer_size


    @staticmethod
    def create_engine(ri : RunningInstance, transaction_callback = None, deploy_callback = None): #nfa : nfa.NFA, blockchain_configuration : Configuration, transaction_callback = None, deploy_callback = None):

        nfa = ri.choreography.to_nfa(optimize=True)
        #nfa.remove_epsilon_transitions()
        #nfa.remove_unreachable_states()

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
        #account = Account.from_key(blockchain_configuration.private_key)
        account = blockchain_configuration.get_account()
        balance = e._w3.eth.get_balance(account.address) 
        print(f"Account: {account.address} . Balance: {e.w3.from_wei(balance, 'ether')} ETH")
        #e._stats = []

        #breakpoint()
        e._transaction_callback = transaction_callback
        e._deploy_callback = deploy_callback

        e.running_instance = ri
        e.save()

        return e


##    def load_smart_contracts(self, nfa_address, nfa_abi, enforcer_address, enforcer_abi):
##
##        self._nfa_abi = nfa_abi
##        self._nfa_address = nfa_address
##        self._enforcer_abi = enforcer_abi
##        self._enforcer_address = enforcer_address
##

    def deploy_smart_contracts(self):

        if not self._nfa:
            raise Exception("No NFA has been set for this purpose")

        scg: SmartContractGenerator = SmartContractGenerator(self._nfa)
        compiled_sol = scg.createSmartContract().compile(debug=self._debug)
        
        #breakpoint()
        self._nfa_abi, self._nfa_bytecode = self.__get_abi_and_bytecode(compiled_sol, "_NFA")
        
        self._enforcer_abi, self._enforcer_bytecode = self.__get_abi_and_bytecode(compiled_sol, "Enforcer")

        len_enforcer = len(self._enforcer_bytecode)
        #len_nfa  = len(self._nfa_bytecode)

        #print(f"NFA contract: {len_nfa} bytes")
        print(f"Enforcer contract: {len_enforcer} bytes")
        #print(f"Total bytecode to deploy: {len_nfa + len_enforcer} bytes")

    
        #breakpoint()
        # 1. deploy NFA contracta
        # TODO skip, no need to deploy NFA contract ...
        #self._nfa_address = self.deployContractNFA(self._nfa_abi, self._nfa_bytecode)
        #print(f"NFA contract deployed ...")    

        # 2. init NFA transitions    
        #self.w3.eth.contract(
        #        address = self._nfa_address,
        #        abi = self._nfa_abi
        #    ).functions.initTransitions().call()
        #print(f"NFA transitions initialized ...")

        # 3. deploy Enforcer contract (passing address of NFA contract)
        #self._enforcer_address = self.deployContractEnforcer(self._enforcer_abi, self._enforcer_bytecode) #, self._nfa_address)
        self._enforcer_address = self.__deployContract("Enforcer", self._enforcer_abi, self._enforcer_bytecode) #, self._nfa_address)

        self._enforcer_contract = self.w3.eth.contract(
                address = self._enforcer_address,
                abi = self._enforcer_abi
            )

        print(f"Enforcer contract deployed ...")

        self._nfa_address = self._invoke_enforcer_function("getNFA")


        self._nfa_contract = self.w3.eth.contract(
                address = self._nfa_address,
                abi = self._nfa_abi
            )

        print(f"NFA address fetched ...")

#        breakpoint()

    def attach_smart_contracts(self, sc_enforcer_address):

        # TODO test and review this code -FS

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


    def _encode_state(self, value):

        if not self._nfa:
            raise Exception("No NFA has been set for this purpose")

        if isinstance(value, nfa.State):
            value = value.id

        return sorted(map(lambda s: s.id, self._nfa.states)).index(value)

    def _encode_action(self, value):
        
        if value == "!":
            return 1
        elif value == "?":
            return 2
        else:
            raise ValueError(f"Unhandled action: {value}")

    def _encode_agent(self, value):

        if not self._nfa:
            raise Exception("No NFA has been set for this purpose")

        return 1 + sorted(self._nfa.agents).index(value)

       
    def _encode_message(self, value):

        if not self._nfa:
            raise Exception("No NFA has been set for this purpose")

        return 1 + sorted(self._nfa.messages).index(value)

    def get_execution_started(self):
##        start_time = self.w3.eth.contract(
##                address = self.enforcer_address,
##                abi = self.enforcer_abi
##            ).functions.getStartTime().call()
##        return datetime.fromtimestamp(start_time)
        start_time = self._invoke_enforcer_function("getStartTime")
        
        return datetime.fromtimestamp(start_time)


    def get_execution_ended(self):
##        try:
##            enforcer_address = self.enforcer_address
##            enforcer_abi = self.enforcer_abi
##
##            if enforcer_address and enforcer_abi:
##                end_time = self.w3.eth.contract(
##                    address = enforcer_address,
##                    abi = enforcer_abi
##                ).functions.getEndTime().call()    
##        
##                return datetime.fromtimestamp(end_time) if end_time else None
##            else:
##                print(f"Enforcer contract not ready for function invokation")
##                return None
##        except Exception:
##            print(f"Error invoking smart contract function:")
##            traceback.print_exc()
##            return None

        end_time = self._invoke_enforcer_function("getEndTime")
        return datetime.fromtimestamp(end_time) if end_time else None

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
        if self.log_file:
            with open(self.log_file, 'a', encoding="utf-8") as f:
                    f.write(f"{self._runID};{self.chain_id};{timezone.now()};{type};{contractAddress};{gasUsed};{cost};{executionTime}\n")
                    #f.write(tabulate(self._stats, headers=["Transaction", "Contract Address", "Gas Used", "Cost (Eth)", "Execution Time (s)", ""],tablefmt="tsv"))
                    #f.write("\n")
    
    def __add_statistics(self, contractAddress, gasUsed, cost, executionTime, type = None):
        #breakpoint()
        self.stats.append([type, contractAddress, gasUsed, float(cost), executionTime])
    
    def __sendTransaction(self, transaction):

        #breakpoint()

        # Send the transaction
        #tx_hash = self.w3.eth.send_raw_transaction(sign_transaction.rawTransaction)

        tx_hash = None
        retries = 3

        #breakpoint()
        while tx_hash is None and retries > 0:

            try:

                nonce = self.w3.eth.get_transaction_count(self.address, "pending") # FS added pending, trying to solve the "nonce too low" problem
                transaction["nonce"] = nonce

                # Sign the transaction
                sign_transaction = self.w3.eth.account.sign_transaction(transaction, private_key = self.private_key)
                
                tx_hash = self.w3.eth.send_raw_transaction(sign_transaction.raw_transaction)

            except web3.exceptions.Web3RPCError as err:
                retries = retries - 1
                if str(err).contains("nonce too low"):
                    print(f"Nonce too low. Try again. Details: {err} ...")
                else:
                    raise err

        if not tx_hash:
            raise Exception(f"Cannot sign transaction after several retries.")
            
        
        # NB cannot sign the transaction explicitly, otherwise the nonce must be computed manually; this is
        #    left to the middlewares (i.e. NonceManager and SignAndSendRawMiddleware)
        #tx_hash = self.w3.eth.send_transaction(transaction)
        
        print(f"Transaction hash: {tx_hash.hex()}. Wait for validation ...")
        # Wait for the transaction to be mined, and get the transaction receipt
        tx_receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=600)
        print(f"Transaction validated. Receipt: {tx_receipt}")

        #breakpoint()
        if self._transaction_callback:
            self._transaction_callback(tx_hash, tx_receipt)

        return tx_receipt

    def __deployContract(self, contract_name : str, abi, bytecode, arguments = None): #address = None):
        #create the contract
        contract = self.w3.eth.contract(abi=abi, bytecode=bytecode)

        gas_price = self.w3.eth.gas_price
        print(f"Gas price: {gas_price}")

        block_gas_limit = self.w3.eth.get_block("latest")["gasLimit"]
        print(f"Block Gas Limit: {block_gas_limit}")

        balance = self.w3.eth.get_balance(self.address)
        balance_eth = self.w3.from_wei(balance, 'ether')
        print(f"Account: {self.address} . Balance (before deployment): {balance_eth} ETH")

        start_time = time.time()
        # build transaction
        #if (address == None):
        tx = {
            "chainId": self.w3.eth.chain_id, #self.chain_id,
            #"gasPrice": gas_price, #self.w3.eth.gas_price,
            "gas": int(0.9 * block_gas_limit), #60000000,
            "from": self.address,
            "maxFeePerGas": int(gas_price * settings.GAS_MAX_FEE_MULTIPLIER),
            "maxPriorityFeePerGas": self.w3.eth.max_priority_fee,

        }
        print(f"Transaction parameters: {tx}")
        #breakpoint()
        if (arguments == None):
#            transaction = contract.constructor().buildTransaction(
            transaction = contract.constructor().build_transaction(tx)
        else:
#            transaction = contract.constructor(address).buildTransaction(
#            transaction = contract.constructor(address).build_transaction(
            transaction = contract.constructor(*arguments).build_transaction(tx)

        #breakpoint()
        gas = self.w3.eth.estimate_gas(transaction)
        print(f"Estimated gas: {gas}.")
#        transaction.update({
#            "maxFeePerGas": int(gas_prices * settings.GAS_MAX_FEE_MULTIPLIER),
#            "maxPriorityFeePerGas": int(gas_prices * settings.GAS_PRIORITY_FEE_MULTIPLIER),
#            #"gas": gas * settings.GAS_MULTIPLIER    
#        })

        transaction.update({"gas": int(gas * settings.GAS_MULTIPLIER)})

        transaction_estimate_cost = round(self.w3.from_wei(gas * gas_price, "ether"), 6)

        print(f"GAS price (estimate): {gas_price} wei")
        print(f"Transaction cost (estimate): {transaction_estimate_cost} ETH")

        build_time = time.time() - start_time
        self._debug_log(f"\nDeploying contract {contract_name} (bytecode: {len(bytecode)} bytes) ...")
        tx_receipt = self.__sendTransaction(transaction)

        gas_price_actual = tx_receipt.effectiveGasPrice
        transaction_actual_cost = round(self.w3.from_wei(tx_receipt.gasUsed * gas_price_actual, 'ether'), 6)

        print(f"GAS price (actual): {gas_price_actual} wei")
        print(f"Transaction cost (actual): {transaction_actual_cost} ether")

        balance = self.w3.eth.get_balance(self.address)
        balance_eth = self.w3.from_wei(balance, 'ether')
        print(f"Account: {self.address} . Balance (after deployment): {balance_eth} ETH")

        execution_time = time.time() - start_time

        self.__add_statistics(tx_receipt.contractAddress ,tx_receipt.gasUsed, transaction_actual_cost, round(execution_time,3), f"Contract Creation")
        self.__log(tx_receipt.contractAddress ,tx_receipt.gasUsed, round(self.w3.from_wei(tx_receipt.gasUsed * self._w3.eth.gas_price, 'ether'),2), round(execution_time,3),f"Contract Creation")
        self._debug_log(f"Done! Contract deployed to {tx_receipt.contractAddress}\n")
        return tx_receipt.contractAddress
##
## stale code -FS
## 
##    def deployContractNFA(self, abi, bytecode):
##        return self.__deployContract("_NFA", abi, bytecode)
##    
##    def deployContractEnforcer(self, abi, bytecode): #, nfa_address : str):
##        return self.__deployContract("Enforcer", abi, bytecode) #, arguments=(nfa_address,))
##

    @property
    def buffer(self):
        return self.get_buffer_items()

    def _invoke_contract_function(self, contract, function_name, function_args=None):

        #breakpoint()
        try:

            if not contract:
                raise Exception(f"No contract specified")

            if not hasattr(contract.functions, function_name):
                raise Exception(f"Smart contract does not have the specified function: {function_name}")

            the_function = getattr(contract.functions, function_name)
            function_args = function_args or []
            res = the_function(*function_args).call()
            return res

        except Exception as err:
            #breakpoint()
            raise Exception(f"Error invoking smart contract function: {function_name}. Details: {err}")
            #print(f"Error invoking Enforcer contract function: {function_name}")
            #traceback.print_exc()
            #return None



    def _invoke_enforcer_function(self, function_name, function_args=None):
        if not self._enforcer_contract:
            raise Exception(f"No enforcer contract defined. Not ready for this method")
        return self._invoke_contract_function(self._enforcer_contract, function_name, function_args)

    def _invoke_nfa_function(self, function_name, function_args=None):
        if not self._nfa_contract:
            raise Exception(f"No NFA contract defined. Not ready for this method")

        return self._invoke_contract_function(self._nfa_contract, function_name, function_args)
            

    # INTERFACE methods

    def ended(self):
        return self._invoke_nfa_function("isEnded")

    def get_all_states(self):
        #return self._invoke_nfa_function("getStates")
        return self._invoke_enforcer_function("getNFAStates")

    def get_curr_states(self):
        #return self._invoke_nfa_function("getCurrentStates")
        return self._invoke_enforcer_function("getNFACurrentStates")

    def get_transitions(self):
        return self._nfa.transitions # TODO FS

    def is_state_final(self, s):

        state_encoded = self._encode_state(s)
        return self._invoke_nfa_function("isFinal", [state_encoded])

    def is_state_initial(self, s):  

        state_encoded = self._encode_state(s)
        return self._invoke_nfa_function("isInitial", [state_encoded])

    def is_state_current(self, s):
    
        state_encoded = self._encode_state(s)

        return self._invoke_nfa_function("isCurrent", [state_encoded])

    def get_buffer_items(self):
##        # TODO refactor this code to use self._invoke_enforcer_function ...
##        enforcer = self.w3.eth.contract(
##                address = self.enforcer_address,
##                abi = self.enforcer_abi
##            )
##
##        actors = enforcer.functions.getActors().call()
##
##        messages = enforcer.functions.getMessages().call()
##
##        items = []
##
##        for actor in actors:
##            for message in messages:
##                # TODO this code should be fixed; the buffer does not contain a counter, anymore
##                counter = enforcer.functions.get_buffer_item(actor, message).call()
##                for i in range(counter):
##                    items.append((actor, message))
##        return items
        return self._invoke_enforcer_function("getBuffer")

    def get_kb(self):
        return self._invoke_enforcer_function("getKB")


    #PROCESSORS

    def process_input(self, precondition, event, knowledge):

        if not self._enforcer_contract:
            raise Exception(f"No enforcer contract defined. Not ready for this method")

        start_time = time.time()

        parts = re.split(r'([!?])', event)

        if len(parts) != 3:
            raise ValueError(f"Unhandled event: {event}")

        agent = self._encode_agent(parts[0])
        action = self._encode_action(parts[1])
        message = self._encode_message(parts[2])

#        transaction = self._enforcer_contract.functions.process_input(precondition or "", event, knowledge or []).build_transaction({
        transaction = self._enforcer_contract.functions.process_input(agent, action, message).build_transaction({
                        "chainId": self.w3.eth.chain_id, #self.chain_id,
                        "from": self.address,
                        "gasPrice": self.w3.eth.gas_price,
                    })
        build_time = time.time() - start_time

        #event = f"{actor}{action}{message}"
        #if precondition:
        #    event = f"{precondition}:{event}"
        #if knowledge:
        #    event = f"{event}({knowledge})"

        self._debug_log(f"\nProcess input {precondition}:{event}({knowledge}) ...")
        tx_receipt = self.__sendTransaction(transaction)
        execution_time = time.time() - start_time
        self.__add_statistics(tx_receipt.contractAddress ,tx_receipt.gasUsed, round(self.w3.from_wei(tx_receipt.gasUsed * self._w3.eth.gas_price, 'ether'),2), round(execution_time,3), f"Process input: {event}")
        self.__log(tx_receipt.contractAddress ,tx_receipt.gasUsed, round(self.w3.from_wei(tx_receipt.gasUsed * self._w3.eth.gas_price, 'ether'),2), round(execution_time,3), f"Process input: {event}")
#        return enforcer.events.outputEvent().processReceipt(tx_receipt)
        logs = self._enforcer_contract.events.outputEvent().process_receipt(tx_receipt)

        self._debug_log(logs[0].args.debug)
        #breakpoint()
        out = logs[0].args.messageOut
        out = None if out == "None" else out

        self.save()
        return out
 

    def process_check(self):

        if not self._enforcer_contract:
            raise Exception(f"No enforcer contract defined. Not ready for this method")

        start_time = time.time()
#        transaction = enforcer.functions.process_check().buildTransaction({
        transaction = self._enforcer_contract.functions.process_check().build_transaction({
                        "chainId": self.w3.eth.chain_id, #self.chain_id,
                        "from": self.address,
                        "gasPrice": self.w3.eth.gas_price,
                    })
        build_time = time.time() - start_time

        self._debug_log(f"\nProcess check ...")
        tx_receipt = self.__sendTransaction(transaction)
        execution_time = time.time() - start_time
        self.__add_statistics(tx_receipt.contractAddress ,tx_receipt.gasUsed, self.w3.from_wei(tx_receipt.gasUsed * self._w3.eth.gas_price, 'ether'), round(execution_time,3), f"Process check")
        self.__log(tx_receipt.contractAddress ,tx_receipt.gasUsed, self.w3.from_wei(tx_receipt.gasUsed * self._w3.eth.gas_price, 'ether'), round(execution_time,3), f"Process check")
        logs = self._enforcer_contract.events.outputEvent().process_receipt(tx_receipt)

        if len(logs) > 0:
            self._debug_log(logs[0].args.debug)
            out = logs[0].args.messageOut
            out = None if out == "None" else out
        else:
            out = None

        self.save()
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
