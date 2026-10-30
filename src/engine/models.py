from decimal import Decimal
from django.db import models
#from django.utils.translation import ugettext as _
from django.utils.translation import gettext as _
from django.utils import timezone
from eth_account import Account
from web3 import Web3, HTTPProvider
from urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter
import random
import time

from web3.exceptions import Web3RPCError 
#from web3.middleware import SignAndSendRawMiddlewareBuilder
#from web3.middleware.signing import NonceManager
from django.core.serializers.json import DjangoJSONEncoder

import re
from picklefield.fields import PickledObjectField
from django.core.exceptions import ValidationError
from bpmn_parser.models import Choreography
from mpst.models import StateVar, MPST, PruningRelation, Transform
from django.db import transaction
from django.conf import settings

from datetime import datetime
from generator import SmartContractGenerator, MPSTSmartContractGenerator
import uuid
import nfa
import rei
import json
import time
import logging
import traceback
import requests
from functools import wraps

from hexbytes import HexBytes
from web3.datastructures import AttributeDict

def w3_to_json(obj):
    if isinstance(obj, HexBytes):
        return obj.hex()
    if isinstance(obj, bytes):
        return obj.hex()
    if isinstance(obj, AttributeDict):
        return {k: w3_to_json(v) for k, v in obj.items()}
    if isinstance(obj, dict):
        return {k: w3_to_json(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [w3_to_json(v) for v in obj]
    return obj

class Configuration(models.Model):

    label = models.CharField(max_length=100, null=True, blank=False, verbose_name=_("label"))
    url = models.CharField(max_length=1000, help_text=_("the RPC URL of the desired blockchain (see https://www.alchemy.com/chain-connect)"), verbose_name=_("url"))
    chain_id = models.CharField(max_length=50, help_text=_("this is a configuration of the chosen blockchain (see https://www.alchemy.com/chain-connect)"), verbose_name=_("chain id"))
    address = models.CharField(max_length=50, help_text=_("this is your wallet address; you can use Metamask or other tools to create one"), verbose_name=_("address"))
    private_key = models.CharField(max_length=500, help_text=_("this is supposed to be a secret; after saving the configuration, it will be hidden"), verbose_name=_("private key"))

    #DEFAULT_RETRIES = 2

    class Meta:
        verbose_name = _("configuration")
        verbose_name_plural = _("configurations")

    @property
    def w3(self):
        w3 = getattr(self, "_w3", None)
        if not w3:
            self._w3 = self.get_w3()

        return self._w3

    def __str__(self):
        short_url = self.url if len(self.url) < 20 else self.url[:20] + "..."
        return self.label or short_url

    def get_account(self):
        account = Account.from_key(self.private_key)
        return account

    def get_w3(self):
            
        # setup a session with retries, to handle occasional disconnections or issues on the network stack
        session = requests.Session()
        retries = Retry(
            total=settings.DEFAULT_RETRIES,
            backoff_factor=0.5,          # 0.5, 1, 2, 4, 8s between retries
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["POST"],     # web3 calls are POST
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retries, pool_connections=10, pool_maxsize=10)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
       
        provider = Web3.HTTPProvider(self.url, session=session, request_kwargs={'timeout': 30})

        print(f"\nConnecting to {self.url} ...")
        w3 = Web3(provider)

        # NB not needed; w3 v7.5 now computes nonce automatically if you don't specify
        # Add automatic nonce management
        #w3.middleware_onion.add(NonceManager())

        # Add automatic signing + sending
        #account = self.get_account()
        #sign_and_send_mw = SignAndSendRawMiddlewareBuilder().build(account)
        #w3.middleware_onion.add(sign_and_send_mw)

        return w3

    def sync(self):
        try:
            while self.w3.eth.syncing:
                print("**> Syncing...") #, w3.eth.syncing)
                #breakpoint()
        except Exception as e:
            print("**> eth_syncing unsupported or failed:", e)
            #breakpoint()


        time.sleep(2) # extra time to allow blockchain to sync ... TODO refactor to avoid arbitrary sleep
 

    def estimate_gas_limit(self, transaction):

        if settings.ENABLE_GAS_ESTIMATION:
            try:
                gas_limit = self.w3.eth.estimate_gas(transaction)
            except Exception as err:
                print(f"Error estimating gas limit: {err}. Assuming default: {settings.DEFAULT_GAS_LIMIT}")
                gas_limit = settings.DEFAULT_GAS_LIMIT
        else:
            gas_limit = settings.DEFAULT_GAS_LIMIT # FS- added to avoid timeout during estimate_gas ...
    
        return gas_limit


    def _sendTransaction(self, transaction): #callback=None):

        #breakpoint()

        # Send the transaction
        #tx_hash = self.w3.eth.send_raw_transaction(sign_transaction.rawTransaction)

        tx_hash = None
        retries = 3

        #breakpoint()
        tx = None
        while tx_hash is None and retries > 0:

            try:

                nonce = self.w3.eth.get_transaction_count(self.address, "pending") # FS added pending, trying to solve the "nonce too low" problem
                transaction["nonce"] = nonce

                # Sign the transaction
                sign_transaction = self.w3.eth.account.sign_transaction(transaction, private_key = self.private_key)
                
                tx_hash = self.w3.eth.send_raw_transaction(sign_transaction.raw_transaction)

                tx = Transaction.objects.create(nonce=nonce, blockchain_configuration=self, transaction_hash=tx_hash.hex(), transaction=w3_to_json(transaction))

            except Web3RPCError as err:
                retries = retries - 1
                if "nonce too low" in str(err):
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

        tx_receipt = None
        try:
            tx_receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=300)
            print(f"Transaction validated. Receipt received ...") #: {tx_receipt}")

            tx.receipt = w3_to_json(tx_receipt)
            tx.receipt_hash = tx_receipt.transactionHash.hex()
            tx.gas_used = tx_receipt.gasUsed
            tx.gas_price = tx_receipt.effectiveGasPrice
            tx.save()
        except Exception:
            print(f"Unable to validate transaction (tx_hash={tx_hash}). Still pending ...")
            traceback.print_exc()

        #breakpoint()
        #if callback:
        #    callback(tx_hash, tx_receipt)

        #return tx_receipt

        return tx, tx_receipt

    def _get_events(self, w3_contract, tx_receipt):
        
        #breakpoint()
        res = []
        event_list = filter(lambda it: it["type"] == "event", w3_contract.abi)
        for ev_desc in event_list:
            events = getattr(w3_contract.events, ev_desc["name"]).process_receipt(tx_receipt)
    
            for curr in events:
                #breakpoint()
                parts = []
                for key,value in sorted(curr["args"].items()):
                    text = value
                    if key:
                        text = f"{key} => {value}"
                    parts.append(text)

                res.append(", ".join(parts))

                #result = ", ".join(f"{key}=>{value}" for key, value in sorted(curr["args"].items()))
                #res.append(result)
            #res.extend(events)

        return res


class RunningInstance(models.Model):

    blockchain_configuration = models.ForeignKey(Configuration, null=True, blank=True, on_delete=models.SET_NULL, verbose_name=_("configuration"))

    label = models.CharField(max_length=500, null=True, blank=True)
    choreography = models.ForeignKey(Choreography, null=True, blank=False, on_delete=models.DO_NOTHING)
    mpst = models.ForeignKey(MPST, null=True, blank=False, on_delete=models.SET_NULL) #on_delete=models.DO_NOTHING)
    running = models.BooleanField(default=False)

    input_events = models.JSONField(default=list, verbose_name=_("input events"))
    output_events = models.JSONField(default=list, verbose_name=_("output events"))
 
    created_at = models.DateTimeField(null=True, blank=False, auto_now_add=True, help_text=_("The time when the running instance has been created"))

    class Meta:
        verbose_name = _("running instance")
        verbose_name_plural = _("running instances")

    @property
    def engine(self):
        e_on = getattr(self, "engineonchain", None)
        e_off = getattr(self, "engineoffchain", None)
        e_on_mpst = getattr(self, "engineonchainmpst", None)
        e_off_mpst = getattr(self, "engineoffchainmpst", None)


        return e_on or e_off or e_on_mpst or e_off_mpst

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

        if not enforcer:
            raise Exception("Non-null enforcer expected")

        if self._enforcer and self.execution_ended:
            raise Exception("Setting an enforcer for running instances that already ended is not supported")

        self._enforcer = enforcer
        if not self.running:
            self.running = True

#        if not self.execution_started and enforcer.engine:
#            self._execution_started = enforcer.engine.get_execution_started()
#            self.execution_started = datetime.now() # FS this is true when a new enforcer has been deployed, it may be not true in case of an enforcer attached to a running smart contract

##    @property
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
        nfa = None
        if self._enforcer and self._enforcer.engine:
            nfa = self._enforcer.engine.nfa
        elif self.engine:   
            nfa = self.engine.nfa
        return nfa
        #return self._enforcer.engine.nfa if self._enforcer else None

    @property
    def global_type(self):
        return self.mpst.root if self.mpst else None

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


    def append_input(self, new_input):
        if not self.input_events:
            self.input_events = []

        self.input_events.extend(re.split(r'[ ]+', new_input.strip()))
        self.save()

    def append_output(self, new_output):
        if not self.output_events:
            self.output_events = []

        #self.output_events.extend(re.split(r'[ ]+', str(new_output)))#.strip()))
        if isinstance(new_output, str):
            self.output_events.extend(re.split(r'[ ]+', str(new_output)))#.strip()))
        elif isinstance(new_output, list):
            self.output_events.extend(new_output)
        else:
            self.output_events.append(new_output)

        self.save()

    def setup_onchain(self, blockchain_configuration : Configuration, **kwargs):

        if not blockchain_configuration:
            raise Exception("Expected non-null blockchain configuration")

        engine_offchain = getattr(self, "engineoffchain", None)
        engine_onchain = getattr(self, "engineonchain", None)

        assert engine_offchain is None, "Cannot run setup_onchain on an off-chain engine"

 
        self.blockchain_configuration = blockchain_configuration
        self.save()

        #breakpoint()
        if not engine_onchain:
    
            if self.choreography and self.mpst:
                raise Exception("Cannot handle a running instance with both a choreography and a MPST")
            elif self.choreography: 
                engine_onchain = EngineOnChain.create_engine(self, the_filter=kwargs.get("filter", None))
            elif self.mpst:
                engine_onchain = EngineOnChainMPST.create_engine(self)
            else:
                raise Exception("Cannot handle a running instance with neither a choreography nor a MPST")
    
            assert engine_onchain is not None      

            engine_onchain.deploy_smart_contracts()
        else:
 
            # TODO test this, not verified yet
            engine_onchain.attach_smart_contracts() #contract_nfa, contract_enforcer)

    
        log_file = kwargs.get("log_file", None) 
        if log_file:
            if not os.path.exists(log_file):
                with open(log_file, "w", encoding="utf-8") as f:
                    f.write("Run;Blockchain;Time;Transaction;Contract Address;Gas Used;Cost;Execution Time\n")

            engine_onchain.set_log_file(log_file)


        return engine_onchain
    

    def setup_offchain(self, **kwargs):

        if self.pk is None:
            raise Exception("This method can be invoked only after saving the instance a first time")

        engine_offchain = getattr(self, "engineoffchain", None)
        engine_onchain = getattr(self, "engineonchain", None)

        assert engine_onchain is None, "Cannot run setup_onchain on an off-chain engine"

        #breakpoint()
        if not engine_offchain:
    
            #breakpoint()

            if self.choreography and self.mpst:
                raise Exception("Cannot handle a running instance with both a choreography and a MPST")
            elif self.choreography: 
                engine_offchain = EngineOffChain.create_engine(self, the_filter=kwargs.get("filter", None))
            elif self.mpst:
                engine_offchain = EngineOffChainMPST.create_engine(self)
            else:
                raise Exception("Cannot handle a running instance with neither a choreography nor a MPST")
    
            assert engine_offchain is not None       
    
            log_file = kwargs.get("log_file", None) 
            if log_file:
                engine_offchain.set_log_file(log_file)

        return engine_offchain

    def start(self):
        self.running = True
        self.save()

    def stop(self):
        if not self.running:
            raise Exception("Cannot stop the running instance: it has not been started")
    
        if self.execution_ended:
            raise Exception("Cannot stop the running instance: its execution has been stopped")

        #self.execution_ended = timezone.now()
        self.running = False
        self.save()


    @property
    def stats(self):
        #breakpoint()
        bc_configuration = self.blockchain_configuration.label if self.blockchain_configuration else None

        #lts = self.lts
 
        lts = None
        if self.choreography:
            lts = self.nfa
        elif self.mpst:
            lts = self.global_type

        if not lts:
            raise Exception("Cannot continue. No LTS found")       

        num_states = len(lts.states) if lts else None
        num_transitions = len(lts.transitions) if lts else None
        num_events = len(lts.events) if lts else None
    

        #breakpoint()
        data = { "id": self.id, "engine_id": self.engine.id, "label": self.label, "blockchain_configuration": bc_configuration, "num_states": num_states, "num_transitions": num_transitions, "num_events": num_events }

        if self.engine and self.engine.stats:
            found = filter(lambda curr: "bytecode_size" in curr, self.engine.stats)

            raise Exception("TODO finish below ...")
##            for curr in found:
##                field_name = curr["contract_name"] + "__" + 
##                data[field_name] = curr["bytecode_size"]
##            

        return data



class Filter:

    def match(self, agent, action, message):
        # by default, an instance of Filter is a dummy filter, accepting everything
        return True

    def apply(self, agent, action, message):
        if self.match(agent, action, message):
            return symbol
        else:
            return None

class ActionFilter(Filter):

    ACTIONS = [ "!", "?" ]

    def __init__(self, agent:str=None, action:str=None, message:str=None):

        if action and action not in self.ACTIONS:
            raise ValueError(f"Unsupported filter action ({self.ACTIONS}). Passed: {action}")

        self._agent = None if not agent or agent == "*" else agent
        self._action = None if not action or action == "*" else action
        self._message = None if not message or message == "*" else message



    def __str__(self):
        x = self._agent or "*"
        o = self._action or "*"
        #y = self._target or "*"
        v = self._message or "*"
        return f"<{x},{o},{v}>"
    
    def match(self, agent:str, action:str, message:str):

        if action and action not in self.ACTIONS:
            raise ValueError(f"Unsupported action ({self.ACTIONS}). Passed: {action}")

        agent_ok = self._agent is None or self._agent == agent
        action_ok = self._action is None or self._action == action
        message_ok = self._message is None or self._message == message

        return agent_ok and action_ok and message_ok

class UnionFilter(Filter):

    def __init__(self, filters):
        if not filters:
            raise Exception("Expected filters")

        for curr in filters:
            if not isinstance(curr, Filter):
                raise Exception(f"Expected filter of type Filter. Passed: {curr}")

        self._filter = filters

    def match(self, agent:str, action:str, message:str):
        return any(lambda curr: curr.match(agent, action, message), self._filters)


class Engine:

    RE_MESSAGE = r"^([^!?]+)([!?])([^!?]+)$"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        #self._nfa = None
        self._lts = None
        self._log_file = None
        self._filter = Filter()


    def _parse_event(self, symbol):
    
        m = re.match(Engine.RE_MESSAGE, symbol)

        return m.groups() if m else (None, None, None)
 

    def get_all_states(self):
        #return self._nfa.states
        return self.curr_states


    def get_transitions(self):
        #return self._nfa.transitions
        return self._lts.transitions

    def is_state_final(self, s):
        #return self._nfa.is_final(s)
        return self._lts.is_final(s)

    def is_state_initial(self, s):  
        #return self._nfa.is_initial(s)
        return self._lts.is_initial(s)

    @property
    def filter(self):
        return self._filter

    def set_filter(self, the_filter : Filter):
        if not the_filter:
            raise Exception("Expected non-null filter")

        self._filter = the_filter

    @property
    def log_file(self):
        return self._log_file

    def set_log_file(self, log_file):
        self._log_file = log_file
        

    @property
    def nfa(self):
        if self._lts is not None and not isinstance(self._lts, nfa.NFA):
            raise Exception("The current LTS is not an NFA")

        #return self._nfa
        return self._lts

    def set_nfa(self, nfa):
        #self._nfa = nfa
        self._lts = nfa

    @property
    def lts(self):
        return self._lts

    def set_lts(self, lts):
        self._lts = lts

    @property
    def history(self):
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

    def get_curr_states(self):
        raise Exception("This is an abstract method, you should implement it")

    def is_state_current(self, s):
        raise Exception("This is an abstract method, you should implement it")

    def some_state_is_current(self, states):
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


class StateVarEncoder(DjangoJSONEncoder):
    def default(self, obj):
        if isinstance(obj, StateVar):
            return obj.id
        return super().default(obj)


class EngineOffChainMPST(Engine, models.Model):

    RE_MESSAGE_MPST = r"^([^!?]+)(([!?])([^!?]+)(->|<-)([\w]+))$"

    running_instance = models.OneToOneField(RunningInstance, null=True, blank=True, on_delete=models.SET_NULL, verbose_name="running instance")
    curr_states = models.JSONField(default=list, encoder=StateVarEncoder, verbose_name=_("current states"))
    history = models.JSONField(default=list, verbose_name=_("history"))
    buffer = models.JSONField(default=dict, verbose_name=_("buffer"))
    kb = models.JSONField(default=dict, verbose_name=_("knowledge base"))

    execution_started = models.DateTimeField(null=True, blank=True, help_text=_("The time when the instance was started, if it was ever executed"))
    execution_ended = models.DateTimeField(null=True, blank=True, help_text=_("The time when the instance was started, if it was ever executed"))

    created_at = models.DateTimeField(null=True, blank=False, auto_now_add=True, help_text=_("The time when the engine has been created"))

    stats = models.JSONField(default=list)

    @staticmethod
    def create_engine(ri : RunningInstance, the_filter : Filter = None): 

        gt = ri.mpst.root

        e = EngineOffChainMPST()
        e.set_global_type(gt)

        e.buffer = {}

        #e.curr_states = list(set([ lts.initial.id ]))
        e._debug : bool = True
        e.stats = []
    
        # do not add filters for the MPST case (for now)
        #if the_filter:
        #    e.set_filter(the_filter)

        e.running_instance = ri
        e.kb = []

        e.execution_started = timezone.now()

        #breakpoint()
        e.process_check() # let the engine make progress as much as possible, without input

        e.save()

        return e
 
    def _parse_event(self, symbol):
    
        #breakpoint()
        m = re.match(EngineOffChainMPST.RE_MESSAGE_MPST, symbol)

        return m.groups() if m else (None, None, None, None, None, None)
 
   
    def set_global_type(self, gt):

        self._global_type = gt
        self._local_types = {}
        self.curr_states = {}
        self.pruning_relation = {}

        for p in gt.participants:
            lt = gt.project(p)
            self._local_types[p] = lt
            self.curr_states[p] = [ lt.initial ]
            self.pruning_relation[p] = PruningRelation()


    def _log_stats(self, obj : dict):
        obj = json.loads(json.dumps(obj, cls=DjangoJSONEncoder))
        self.stats.append(obj)


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

    def _buffer_add(self, precondition, actor : str, action: str, message : str, knowledge):
        #breakpoint() # TODO test code below

        assert action in [ "!", "?" ], f"Unexpected action: {action}"

        num_before = len(self.get_buffer_items())

        if actor not in self.buffer:
            self.buffer[actor] = {}

        if action not in self.buffer[actor]:
            self.buffer[actor][action] = {}

        if message not in self.buffer[actor][action]:
            self.buffer[actor][action][message] = []

        self.buffer[actor][action][message].append({"precondition": precondition, "knowledge": knowledge})

        num_after = len(self.get_buffer_items())
        assert num_after == num_before + 1, f"Expected buffer length after add operation: {num_before+1}. Actual length: {num_after}"

    def _buffer_remove(self, precondition, actor : str, action : str, message : str, knowledge):

        #breakpoint() # TODO test code below
 
        assert action in [ "!", "?" ], f"Unexpected action: {action}"

        if not actor in self.buffer:
            raise Exception(f"No event ({actor},{action},{message}) to remove from buffer")

        if not action in self.buffer[actor]:
            raise Exception(f"No event ({actor},{action},{message}) to remove from buffer")

        if not message in self.buffer[actor][action]:
            raise Exception(f"No event ({actor},{action},{message}) to remove from buffer")

        for (idx,curr) in enumerate(self.buffer[actor][action][message]):
            if curr["precondition"] == precondition and curr["knowledge"] == knowledge:
                del self.buffer[actor][action][message][idx]
                return # successful case

        # if it reaches here, no message with precondition and knowledge was found for actor, thus raise an exception
        raise Exception(f"No event ({actor},{action},{message}) to remove from buffer with given precondition and knowledge")
     
    def get_buffer_items(self):
        #breakpoint() # TODO test the code below
        items = []
        for actor in self.buffer:
            for action in self.buffer[actor]:
                for message in self.buffer[actor][action]:
                    for curr in self.buffer[actor][action][message]:
                        precondition = curr["precondition"]
                        knowledge = curr["knowledge"]
                        items.append((precondition, (actor, action, message), knowledge))

        return items

    
    def ended(self):
        # TODO re-implement this
        print("(* EngineOffChainMPST.ended() not implemented yet *)")
        return False
  
##    
##    def buffer_find_usable_event(self):
##
##        breakpoint() # TODO rewrite code below
##
##        from enforcer import Enforcer
##
##        found = None
##        for actor in self.buffer:
##            for action in self.buffer[actor]:
##                for message in self.buffer[actor][action]:
##                    event = f"{actor}{action}{message}"
##                    for curr in self.buffer[actor][action][message]:
##                        if not "precondition" in curr or not "knowledge" in curr: 
##                            raise Exception(f"Ill-formed buffer item. Expected item with 'precondition' and 'knowledge'. Found: {curr}")
##    
##                        precondition = curr["precondition"]
##                        knowledge = curr["knowledge"]
##                    
##                        for s in self.curr_states:
##                            #if self._nfa.transitions_from(s, event) and self.check_sat(precondition):
##                            if self._lts.transitions_from(s, event) and self.check_sat(precondition):
##                                return precondition, event, knowledge
##                        
##        raise Enforcer.NoMessageFound("No usable message found")
##
   
    def process_input(self, precondition, event_text, knowledge):

        #breakpoint()
        actor,event,action,message,direction,actor1 = self._parse_event(event_text)

        #if actor not in self.curr_states:
        if not actor:
            print(f"(* discard event : {event_text} : format not recognized *)")
            return

        if actor not in self.get_actors(): 
            print(f"(* discard event : {event_text} : actor not known *)")
            return

        if event not in self.get_events():
            print(f"(* discard event : {event_text} : event not allowed *)")
            return

        #transforms_list = list(self._local_types[actor].transforms)
        transforms_list = list(self.get_local_type(actor).transforms)
        random.shuffle(transforms_list)

        # iterate only concat Transforms
        for t in filter(Transform.select_concat, transforms_list):
            #breakpoint()
            if t.is_enabled(self.curr_states[actor], event_text):
                t.apply(self.curr_states[actor], self.pruning_relation[actor], event) # TODO precondition and knowledge not handled, yet
                print(f"(* applied transform: {actor}: {t} *)")
                out = f"{actor}{event}"
                return out

        # if this point is reached, buffer the event
        self._buffer_add(None, actor, action, event, None)

        return None


    def process_check(self):

        #breakpoint()
        dirty = True
        while dirty:
            dirty = False
            #actor_list = list(self._local_types.keys())

            # 1. try consuming buffered events
            for curr in self.get_buffer_items():
                precondition, (actor, action, event), knowledge = curr
                event_text = f"{actor}{event}"

                lt = self.get_local_type(actor)
                transforms_list = list(lt.transforms)
                for t in filter(lambda t: Transform.select_concat(t), transforms_list):
                    #breakpoint()
                    if t.is_enabled(self.curr_states[actor], event_text):
                        t.apply(self.curr_states[actor], self.pruning_relation[actor], event) # TODO precondition and knowledge not handled, yet
                        print(f"(* applied transform: {actor}: {t} (from buffer) *)")
                        self._buffer_remove(precondition, actor, action, event, knowledge)
                        out = f"{actor}{event}"
                        return out
 
                #breakpoint()

            # 2. try with "silent" transforms
            actor_list = self.get_actors()
            random.shuffle(actor_list)
            for actor in actor_list:
                #lt = self._local_types[actor]
                lt = self.get_local_type(actor)
                transforms_list = list(lt.transforms)
                random.shuffle(transforms_list)
                #for t in transforms_list:   
                # iterate only non-concat Transforms
                for t in filter(lambda t: not Transform.select_concat(t), transforms_list):
                    #if not t.is_concat:
                    if t.is_enabled(self.curr_states[actor]):
                        #breakpoint()
                        t.apply(self.curr_states[actor], self.pruning_relation[actor])
                        print(f"(* applied transform: {actor}: {t} *)")
                        dirty = True
                        break
                        
        return None

    def get_actors(self):
        return list(self._local_types.keys())

    def get_events(self):
        res = []
        for p, lt in self._local_types.items():
            res.extend(lt.events)

        return set(res)

    def get_local_type(self, name : str):
        if name not in self._local_types:
            raise Exception(f"Local type with name {name} does not exist")

        return self._local_types[name]

    def get_all_states(self):
        return sorted(self._global_type.states)

    def get_curr_states(self, participant=None):
        curr_states = []

        if participant:
            curr_states = self.curr_states[participant]
        else:
            for actor, states in sorted(self.curr_states.items()):
                for s in states:
                    curr_states.append(s)
    
        return sorted(set(curr_states))


    def is_state_final(self, s):
        return False # TODO how to check a final state?

    def is_state_initial(self, s):  
        #actor, state = s # split the input state (a pair)
        #return state == self._local_types[actor].initial
        return s == self._global_type.initial

    def is_state_current(self, s, participant=None):  
        #actor, state = s # split the input state (a pair)
        #return state in self.curr_states[actor]

        curr_states = []
        #for name, lt in self._local_types.items():
        for name in self.get_actors():
            lt = self.get_local_type(name)
            curr_states.extend(self.curr_states[name])

        return s in curr_states

    def some_state_is_current(self, states, participant=None):

        curr_states = []
        #for name, lt in self._local_types.items():
        for name in self.get_actors():
            lt = self.get_local_type(name)

            if participant is None or name == participant:
                curr_states.extend(self.curr_states[name])

        res = len(set(curr_states).intersection(states)) > 0
        return res





class EngineOffChain(Engine, models.Model):

    running_instance = models.OneToOneField(RunningInstance, null=True, blank=True, on_delete=models.SET_NULL, verbose_name="running instance")
    curr_states = models.JSONField(default=list, verbose_name=_("current states"))
    history = models.JSONField(default=list, verbose_name=_("history"))
    buffer = models.JSONField(default=dict, verbose_name=_("buffer"))
    kb = models.JSONField(default=list, verbose_name=_("knowledge base"))

    execution_started = models.DateTimeField(null=True, blank=True, help_text=_("The time when the instance was started, if it was ever executed"))
    execution_ended = models.DateTimeField(null=True, blank=True, help_text=_("The time when the instance was started, if it was ever executed"))

    created_at = models.DateTimeField(null=True, blank=False, auto_now_add=True, help_text=_("The time when the engine has been created"))

    stats = models.JSONField(default=list)

    @staticmethod
    def create_engine(ri : RunningInstance, the_filter : Filter = None): 

        e = EngineOffChain()

        nfa = ri.choreography.to_nfa(optimize=True)

        e._lts : nfa.LTS = nfa
        e.buffer = {}

        #breakpoint()
        e.curr_states = list(nfa.e_closure(set([ nfa.initial.id ])))
        e._debug : bool = True
        e.stats = []
    
        if the_filter:
            e.set_filter(the_filter)

        e.running_instance = ri
        e.kb = []

        e.execution_started = timezone.now()

        e.save()

        return e
    

    def _log_stats(self, obj : dict):
        obj = json.loads(json.dumps(obj, cls=DjangoJSONEncoder))
        self.stats.append(obj)


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
   
    def process_input(self, precondition, event, knowledge):

        out = None

        (actor, action, message) = self._parse_event(event)

        match = self._filter.match(actor, action, message)
        if not match:
            return event 

        print(f"Process: {precondition or 'T'} -> {event}({knowledge or 'nil'})")

        if self.condition_rule_send_now(precondition, event):
            out = self.rule_send_now(precondition, event, knowledge)

        elif self.condition_rule_send_delayed(precondition, event):
            out = self.rule_send_delayed(precondition, event, knowledge)

        elif self.condition_rule_receive_now(precondition, event):
            out = self.rule_receive_now(precondition, event, knowledge)

        elif self.condition_rule_receive_delayed(precondition, event):
            out = self.rule_receive_delayed(precondition, event, knowledge)
        else:
            self._debug_log("(* No matching condition *)")        

        self._append_history(out, self.get_curr_states(), []) 

        self.save()
        return out


    def process_check(self):

        from enforcer import Enforcer

        out = None
        try:
            precondition, event, knowledge = self.buffer_find_usable_event()

            (actor, action, message) = self._parse_event(event) #symbol)

            if action == "!": 
                out = self.rule_send_buffered(precondition, actor, message, event, knowledge)
            elif action == "?":
                out = self.rule_receive_buffered(precondition, actor, message, event, knowledge)
            else:
                raise ValueError(f"Unexpected action: {action}")
        except Enforcer.NoMessageFound: #Exception:
            pass

        self._append_history(out, self.get_curr_states(), []) 

        self.save()
        return out

    # UTILS

    def _buffer_add(self, precondition, actor : str, action: str, message : str, knowledge):

        assert action in [ "!", "?" ], f"Unexpected action: {action}"

        num_before = len(self.get_buffer_items())

        if actor not in self.buffer:
            self.buffer[actor] = {}

        if action not in self.buffer[actor]:
            self.buffer[actor][action] = {}

        if message not in self.buffer[actor][action]:
            self.buffer[actor][action][message] = []

        self.buffer[actor][action][message].append({"precondition": precondition, "knowledge": knowledge})

        num_after = len(self.get_buffer_items())
        assert num_after == num_before + 1, f"Expected buffer length after add operation: {num_before+1}. Actual length: {num_after}"

    def _buffer_remove(self, precondition, actor : str, action : str, message : str, knowledge):

        assert action in [ "!", "?" ], f"Unexpected action: {action}"

        if not actor in self.buffer:
            raise Exception(f"No event ({actor},{action},{message}) to remove from buffer")

        if not action in self.buffer[actor]:
            raise Exception(f"No event ({actor},{action},{message}) to remove from buffer")

        if not message in self.buffer[actor][action]:
            raise Exception(f"No event ({actor},{action},{message}) to remove from buffer")

        for (idx,curr) in enumerate(self.buffer[actor][action][message]):
            if curr["precondition"] == precondition and curr["knowledge"] == knowledge:
                del self.buffer[actor][action][message][idx]
                return # successful case

        # if it reaches here, no message with precondition and knowledge was found for actor, thus raise an exception
        raise Exception(f"No event ({actor},{action},{message}) to remove from buffer with given precondition and knowledge")
        
    
    def buffer_find_usable_event(self):

        from enforcer import Enforcer

        found = None
        for actor in self.buffer:
            for action in self.buffer[actor]:
                for message in self.buffer[actor][action]:
                    event = f"{actor}{action}{message}"
                    for curr in self.buffer[actor][action][message]:
                        if not "precondition" in curr or not "knowledge" in curr: 
                            raise Exception(f"Ill-formed buffer item. Expected item with 'precondition' and 'knowledge'. Found: {curr}")
    
                        precondition = curr["precondition"]
                        knowledge = curr["knowledge"]
                    
                        for s in self.curr_states:
                            #if self._nfa.transitions_from(s, event) and self.check_sat(precondition):
                            if self._lts.transitions_from(s, event) and self.check_sat(precondition):
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
        #return self._nfa.is_final(self.curr_states)
        return self._lts.is_final(self.curr_states)

    def get_curr_states(self):
        return self.curr_states

    def is_state_current(self, s):
        #assert isinstance(s, str), f"Expected string as state name. Passed: {s}"
        #if isinstance(s, nfa.State):
        #    s = s.id
        
        res = isinstance(s, str) and (s in self.curr_states)
        return res

    def some_state_is_current(self, states):
        res = len(set(map(lambda s: s.id, states)).intersection(self.curr_states)) > 0# and (s in self.curr_states)
        return res



    def get_buffer_items(self):
        items = []
        for actor in self.buffer:
            for action in self.buffer[actor]:
                for message in self.buffer[actor][action]:
                    for curr in self.buffer[actor][action][message]:
                        precondition = curr["precondition"]
                        knowledge = curr["knowledge"]
                        items.append((precondition, (actor, action, message), knowledge))

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
            #enabled_transitions = self._nfa.transitions_from(curr, event)
            enabled_transitions = self._lts.transitions_from(curr, event)

            if len(enabled_transitions) > 0:

                self._debug_log(f"(* Condition rule send now *)") #: {precondition or 'T'} -> {event} *)")
                return True

        return False

    def condition_rule_send_delayed(self, precondition, event):    

        m = re.match(r"^[^!?]+\![^!?]+$", event) 
        if not m:
            return False

#        if self.check_sat(precondition):
#            return False


        # TODO restrict the loop below to only states that are reachable from current one
        #for curr in self._nfa.states:
        for curr in self._lts.states:
            #enabled_transitions = self._nfa.transitions_from(curr, event)
            enabled_transitions = self._lts.transitions_from(curr, event)
            if len(enabled_transitions) > 0:
                self._debug_log(f"(* Condition rule send delayed *)") #: {precondition or 'T'} -> {event} *)")
                return True


        return False 


    def condition_rule_receive_now(self, precondition, event):

        if not self.check_sat(precondition):
            return False

        m = re.match(r"^[^!?]+\?[^!?]+$", event) 
        if m is None:
            return False

        for curr in self.curr_states:
            #enabled_transitions = self._nfa.transitions_from(curr, event)
            enabled_transitions = self._lts.transitions_from(curr, event)

            if len(enabled_transitions) > 0:

                self._debug_log(f"(* Condition rule receive now *)") #: {precondition or 'T'} -> {event} *)")
                return True

        return False

    def condition_rule_receive_delayed(self, precondition, event):    
    
        m = re.match(r"^[^!?]+\?[^!?]+$", event) 
        if not m:
            return False
    
#        if self.check_sat(precondition):
#            return False

        # TODO restrict the loop below to only states that are reachable from current one
        #for curr in self._nfa.states:
        for curr in self._lts.states:
            #enabled_transitions = self._nfa.transitions_from(curr, event)
            enabled_transitions = self._lts.transitions_from(curr, event)
            if len(enabled_transitions) > 0:
                self._debug_log(f"(* Condition rule receive delayed *)") #: {precondition or 'T'} -> {event} *)")
                return True

        return False #True


    # RULES below

    def rule_send_now(self, precondition, event, knowledge):
        reached = set()
        for s in self.curr_states:

            #s_reached = self._nfa.read_symbol(event, s)
            s_reached = self._lts.read_symbol(event, s)

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
        self._buffer_add(precondition, actor, "!", message, knowledge)
        return ""

    def rule_send_buffered(self, precondition, actor, message, event, knowledge):
        
        assert actor in self.buffer and "!" in self.buffer[actor] and message in self.buffer[actor]["!"]
        
        reached = set()
        for s in self.curr_states:
            #s_reached = self._nfa.read_symbol(event, s)
            s_reached = self._lts.read_symbol(event, s)

            if len(s_reached) == 0:
                self._debug_log(f"(* State {s} was not compatible with event {event} and has been discarded... *)")
            else:
                reached = reached.union(s_reached)
        
        self._buffer_remove(precondition, actor, "!", message, knowledge)

        nd_factor = (len(reached) - len(self.curr_states)) / len(self.curr_states)
        self.curr_states = list(reached)

        self.add_knowledge(knowledge)
        return event


    def rule_receive_now(self, precondition, event, knowledge):

        reached = set()
        for s in self.curr_states:

            #s_reached = self._nfa.read_symbol(event, s)
            s_reached = self._lts.read_symbol(event, s)

            if len(s_reached) == 0:
                self._debug_log(f"(* State {s} was not compatible with event {event} and has been discarded... *)")
            else:
                reached = reached.union(s_reached)
            

        self.curr_states = list(reached)

        self.add_knowledge(knowledge)
        return event

    def rule_receive_delayed(self, precondition, event, knowledge):

        actor, message = event.split("?")
        self._buffer_add(precondition, actor, "?", message, knowledge)
        return ""

    def rule_receive_buffered(self, precondition, actor, message, event, knowledge):
      
        assert actor in self.buffer and "?" in self.buffer[actor] and message in self.buffer[actor]["?"]

        reached = set()
        for s in self.curr_states:
            #s_reached = self._nfa.read_symbol(event, s)
            s_reached = self._lts.read_symbol(event, s)

            if len(s_reached) == 0:
                self._debug_log(f"(* State {s} was not compatible with event {event} and has been discarded... *)")
            else:
                reached = reached.union(s_reached)
        
        self._buffer_remove(precondition, actor, "?", message, knowledge)

        nd_factor = (len(reached) - len(self.curr_states)) / len(self.curr_states)
        self.curr_states = list(reached)

        self.add_knowledge(knowledge)
        return event

class Transaction(models.Model):
    
    created_at = models.DateTimeField(null=False, blank=False, auto_now_add=True, help_text=_("The time when the transaction has been created on the blockchain"))
    transaction = models.JSONField(null=True, blank=False, verbose_name=_("transaction"))
    transaction_hash = models.CharField(max_length=100, null=True, blank=False, verbose_name=_("transaction hash"))
    blockchain_configuration = models.ForeignKey(Configuration, null=True, blank=False, on_delete=models.SET_NULL, verbose_name=_("configuration"))

    validated_at = models.DateTimeField(null=True, blank=True, help_text=_("The time when the transaction has received its transaction receipt from the blockchain"))
    receipt_hash = models.CharField(max_length=100, null=True, blank=True, verbose_name=_("receipt hash"))
    receipt= models.JSONField(null=True, blank=True, default=None, verbose_name=_("receipt"))


    nonce = models.IntegerField(null=True, help_text=_("nonce"))
    gas_used = models.IntegerField(null=True, help_text=_("gas used"))
    gas_price = models.IntegerField(null=True, help_text=_("gas price"))

    @property
    def is_pending(self):
        return self.transaction_hash is not None and self.receipt is None
 

    def check_receipt(self):
        assert self.transaction_hash is not None, "Expected non-null transaction hash"
        assert self.blockchain_configuration is not None, "Expected non-null blockchain configuration"

        w3 = self.blockchain_configuration.get_w3()
        
        tx_receipt = w3.eth.wait_for_transaction_receipt(self.transaction_hash, timeout=30) # NB this may throw TimeoutException
        self.receipt = w3_to_json(tx_receipt)
        self.receipt_hash = self.receipt.transactionHash.hex()
        self.validated_at = timezone.now()
        self.save()

class Contract(models.Model):

    contract_address =models.CharField(max_length=100, null=True, blank=False, verbose_name=_("contract address"))
#    running_instance = models.ForeignKey(RunningInstance, null=True, blank=False, on_delete=models.SET_NULL, verbose_name=_("running instance"))
    blockchain_configuration = models.ForeignKey(Configuration, null=True, blank=True, on_delete=models.SET_NULL, verbose_name=_("configuration"))
    label = models.CharField(max_length=100, verbose_name=_("label"))
    abi = models.JSONField(null=True, blank=False, verbose_name=_("abi"))
    bytecode = models.TextField(null=True, blank=False, verbose_name=_("bytecode"))
    bytecode_hash = models.CharField(max_length=256, null=True, blank=False, verbose_name=_("bytecode hash"))
    deployed_at = models.DateTimeField(null=True, blank=False, auto_now_add=True, help_text=_("The time when the contract has been deployed"))

    DEFAULT_EVENT_NAMES = [ "Debug", ]

    class Meta:
        verbose_name = _("contract")
        verbose_name_plural = _("contracts")
        unique_together = (("contract_address",),)# ("label", "running_instance"))

    def __str__(self):
        return f"{self.label} : {self.contract_address}/{self.label}/{self.id}"


    def create_w3_contract(self):
 
        assert self.blockchain_configuration is not None, "Expected non-empty blockchain Configuration"
        assert self.abi is not None, "Missing ABI"
        assert self.bytecode is not None, "Missing bytecode"

        return self.blockchain_configuration.w3.eth.contract(abi=self.abi, bytecode=self.bytecode)


    def attach_w3_contract(self):
 
        assert self.blockchain_configuration is not None, "Expected non-empty blockchain Configuration"
        assert self.abi is not None, "Missing ABI"
        #assert self.bytecode is not None, "Missing bytecode"
        assert self.contract_address is not None, "Missing contract address"

        #return self.blockchain_configuration.w3.eth.contract(abi=self.abi, bytecode=self.bytecode)
        return self.blockchain_configuration.w3.eth.contract(address=self.contract_address, abi=self.abi)

    @property
    def running_instance(self):
        return self.enforcer_engine.running_instance if self.enforcer_engine else None

    @property
    def choreography(self):
        return self.running_instance.choreography if self.running_instance else None

    @property
    def bytecode_size(self):
        return len(self.bytecode) if self.bytecode else 0


    @staticmethod
    def get_bytecode_hash(bytecode):
        import hashlib
        digest = hashlib.sha256(bytecode.encode("utf-8")).hexdigest()
        return digest

    def deploy(self, arguments=None, callback=None): #, contract_name : str, libraries=None, arguments=None):
        
        assert self.abi is not None, "Missing abi, cannot deploy"
        assert self.bytecode is not None, "Missing bytecode, cannot deploy"

        assert self.blockchain_configuration is not None, "Expected non-empty blockchain configuration"


        print(f"\nDeploying contract {self.label} (bytecode: {len(self.bytecode)} bytes) ...")

        bc = self.blockchain_configuration    
        #abi = self.get_abi(contract_name)

        #libraries = libraries or {}
        #bytecode = self.get_bytecode(contract_name, **libraries)

        w3 = bc.get_w3()
        w3_contract = self.create_w3_contract()
        #contract = w3.eth.contract(abi=self.abi, bytecode=self.bytecode)

        gas_price = w3.eth.gas_price
        print(f"Gas price: {gas_price}")

        block_gas_limit = w3.eth.get_block("latest")["gasLimit"]
        print(f"Block Gas Limit: {block_gas_limit}")

        balance_before = w3.eth.get_balance(bc.address)
        balance_eth = w3.from_wei(balance_before, 'ether')
        print(f"Account: {bc.address} . Balance (before deployment): {balance_eth} ETH")

        ts_begin = datetime.now() #time.time()
        # build transaction
        #if (address == None):

        gas = int(0.9 * block_gas_limit)
        max_fee_per_gas = int(gas_price * settings.GAS_MAX_FEE_MULTIPLIER)

        tx = {
            "chainId": w3.eth.chain_id, #self.chain_id,
            #"gasPrice": gas_price, #self.w3.eth.gas_price,
            "gas": gas, #60000000,
            "from": bc.address,
            "maxFeePerGas": max_fee_per_gas,
            "maxPriorityFeePerGas": w3.eth.max_priority_fee,

        }
        #print(f"Transaction parameters: {tx}")
        #breakpoint()
        if (arguments == None):
#            transaction = contract.constructor().buildTransaction(
            transaction = w3_contract.constructor().build_transaction(tx)
        else:
#            transaction = contract.constructor(address).buildTransaction(
#            transaction = contract.constructor(address).build_transaction(
            transaction = w3_contract.constructor(*arguments).build_transaction(tx)

        #breakpoint()
        #if settings.ENABLE_GAS_ESTIMATION:
        #    gas_transaction_estimate = w3.eth.estimate_gas(transaction)
        #else:
        #    gas_transaction_estimate = settings.DEFAULT_GAS_LIMIT
        gas_transaction_estimate = bc.estimate_gas_limit(transaction)

        gas = int(gas_transaction_estimate * settings.GAS_MULTIPLIER)
        print(f"Estimated gas: {gas}.")
#        transaction.update({
#            "maxFeePerGas": int(gas_prices * settings.GAS_MAX_FEE_MULTIPLIER),
#            "maxPriorityFeePerGas": int(gas_prices * settings.GAS_PRIORITY_FEE_MULTIPLIER),
#            #"gas": gas * settings.GAS_MULTIPLIER    
#        })

        transaction.update({"gas": gas })


        transaction_estimate_cost_wei = gas * gas_price
        transaction_estimate_cost = round(w3.from_wei(transaction_estimate_cost_wei, "ether"), 6)

        print(f"GAS price (estimate): {gas_price} WEI")
        print(f"Transaction cost (estimate): {transaction_estimate_cost} ETH - {transaction_estimate_cost_wei} WEI")

        ts_build_end = datetime.now() #time.time() - start_time
        #tx_receipt = bc._sendTransaction(transaction, callback=callback)
        tx, tx_receipt = bc._sendTransaction(transaction) # callback=callback)

        if not tx_receipt:
            raise Exception("No transaction receipt received. Are you experiencing network problems?")
        elif tx_receipt["status"] == 0:
            raise Exception(f"Failed deployment: status={tx_receipt['status']}. Transaction={tx}. Receipt={tx_receipt}")

        #breakpoint()

        gas_price_actual = tx_receipt.effectiveGasPrice
        transaction_actual_cost_wei = tx_receipt.gasUsed * gas_price_actual
        transaction_actual_cost = round(w3.from_wei(transaction_actual_cost_wei, 'ether'), 6)

        ts_execution_end = datetime.now() #time.time() - start_time

        print(f"GAS price (actual): {gas_price_actual} WEI")
        print(f"Transaction cost (actual): {transaction_actual_cost} ETH - {transaction_actual_cost_wei} WEI")

        balance_after = w3.eth.get_balance(bc.address)
        balance_eth = w3.from_wei(balance_after, 'ether')
        print(f"Account: {bc.address} . Balance (after deployment): {balance_eth} ETH")

        events = bc._get_events(w3_contract, tx_receipt) or []
        for curr in events:
            print(f"**> Event: {curr}")
        

        #self.__add_statistics(tx_receipt.contractAddress ,tx_receipt.gasUsed, transaction_actual_cost, round(execution_time,3), f"Contract Creation")
        #self.__log(tx_receipt.contractAddress ,tx_receipt.gasUsed, round(w3.from_wei(tx_receipt.gasUsed * self._w3.eth.gas_price, 'ether'),2), round(execution_time,3),f"Contract Creation")
        print(f"Done! Contract {self.label} deployed to {tx_receipt.contractAddress}\n")

        self.contract_address = tx_receipt.contractAddress
        self.save()

        stats = {
            "contract_name": self.label,
            "contract_address": tx_receipt.contractAddress,
            "balance_before": balance_before,
            "balance_after": balance_after,  
            "transaction_estimate_cost": transaction_estimate_cost,
            "gas": gas,
            "gas_price_actual": gas_price_actual,
            "max_fee_per_gas": max_fee_per_gas,
            "transaction_actual_cost": transaction_actual_cost,
            "transaction_type": "deploy",
            "bytecode_size": len(self.bytecode),
            "ts_begin": ts_begin,
            "ts_end": ts_execution_end,
            "build_time": (ts_build_end - ts_begin).total_seconds(), # / 1000,
            "execution_time": (ts_execution_end - ts_build_end).total_seconds(), # / 1000,
        }

        #breakpoint()
        return w3_contract, stats
        #return tx_receipt.contractAddress, contract



    def transact(self, function_name, function_args=None):

        assert self.blockchain_configuration is not None, "Expected non-empty blockchain configuration"

        bc = self.blockchain_configuration    
 
        w3 : Web3 = bc.get_w3()

        #start_time = time.time()
        balance_before = w3.eth.get_balance(bc.address)
        balance_eth = w3.from_wei(balance_before, 'ether')
        print(f"Account: {bc.address} . Balance (before deployment): {balance_eth} ETH")

        ts_begin = datetime.now()

        bc = self.blockchain_configuration

        w3_contract = self.attach_w3_contract()
        the_function = getattr(w3_contract.functions, function_name)
        if not the_function:
            raise ValueError(f"Cannot find function '{function_name}'")

        block_gas_limit = w3.eth.get_block("latest")["gasLimit"]
        print(f"Block Gas Limit: {block_gas_limit}")

        gas = int(0.9 * block_gas_limit)
        gas_price = w3.eth.gas_price
        max_fee_per_gas = int(gas_price * settings.GAS_MAX_FEE_MULTIPLIER)

        #function_args = function_args or []
        #breakpoint()
        tx = {
            "chainId": w3.eth.chain_id, #self.chain_id,
            "gas": gas, 
            "from": bc.address,
            #"gasPrice": int(w3.eth.gas_price * 1.5),
            "maxFeePerGas": max_fee_per_gas, 
            "maxPriorityFeePerGas": w3.eth.max_priority_fee,
        }

        if function_args == None:
            transaction = the_function().build_transaction(tx)
        else:
            transaction = the_function(*function_args).build_transaction(tx)

        gas_transaction_estimate = bc.estimate_gas_limit(transaction)
        gas = int(gas_transaction_estimate * settings.GAS_MULTIPLIER)
        print(f"Estimated gas: {gas}.")

####=====
####
####        tx = {
####            "chainId": w3.eth.chain_id, 
####            "gas": gas, #60000000,
####            "from": bc.address,
####            "maxFeePerGas": max_fee_per_gas,
####            "maxPriorityFeePerGas": w3.eth.max_priority_fee,
####
####        }
####        print(f"Transaction parameters: {tx}")
####        #breakpoint()
####        if (arguments == None):
#####            transaction = contract.constructor().buildTransaction(
####            transaction = w3_contract.constructor().build_transaction(tx)
####        else:
#####            transaction = contract.constructor(address).buildTransaction(
#####            transaction = contract.constructor(address).build_transaction(
####            transaction = w3_contract.constructor(*arguments).build_transaction(tx)
####
####====
####

        transaction.update({"gas": gas })

        gas_price = w3.eth.gas_price
        transaction_estimate_cost_wei = gas * gas_price
        transaction_estimate_cost = round(w3.from_wei(transaction_estimate_cost_wei, "ether"), 6)

        print(f"GAS price (estimate): {gas_price} WEI")
        print(f"Transaction cost (estimate): {transaction_estimate_cost} ETH - {transaction_estimate_cost_wei} WEI")

        balance_after = w3.eth.get_balance(bc.address)
        balance_eth = w3.from_wei(balance_after, 'ether')
        print(f"Account: {bc.address} . Balance (after deployment): {balance_eth} ETH")

        #build_time = time.time() - start_time

        print(f"\nProcess check ...")
        tx, tx_receipt = self.blockchain_configuration._sendTransaction(transaction) #, callback=self._transaction_callback)
        ts_execution_end = datetime.now()

        #breakpoint()
        events = bc._get_events(w3_contract, tx_receipt) or []
        for curr in events:
            print(f"**> Event: {curr}")



        gas_price_actual = tx_receipt.effectiveGasPrice
        transaction_actual_cost_wei = tx_receipt.gasUsed * gas_price_actual
        transaction_actual_cost = round(w3.from_wei(transaction_actual_cost_wei, 'ether'), 6)


        print(f"GAS price (actual): {gas_price_actual} WEI")
        print(f"Transaction cost (actual): {transaction_actual_cost} ETH - {transaction_actual_cost_wei} WEI")

        max_fee_per_gas = int(gas_price * settings.GAS_MAX_FEE_MULTIPLIER)


        #execution_time = time.time() - start_time

        _stats = { 
            "contract_name": self.label,
            "contract_address": tx_receipt.contractAddress,
            "function_name": function_name,
            "function_args": function_args,
            "gas": gas,
            "gas_price_actual": gas_price_actual,
            "balance_before": balance_before,
            "balance_after": balance_after,
            "transaction_type": "function",
            "ts_begin": ts_begin,
            "ts_end": ts_execution_end,
            "execution_time": (ts_execution_end - ts_begin).total_seconds(), # / 1000,
            "transaction_actual_cost": transaction_actual_cost,
            "max_fee_per_gas": max_fee_per_gas,
            "transaction_estimate_cost": transaction_estimate_cost,
        }

        return None, _stats # TODO refactor this, use events to get the intended output


    def invoke(self, function_name, function_args=None):

        retries = max(settings.DEFAULT_RETRIES, 1) # at least one attempt ...

        while retries > 0:
            #breakpoint()
            self.blockchain_configuration.sync()
            try:
                w3_contract = self.attach_w3_contract()#self.blockchain_configuration)
                
                if not hasattr(w3_contract.functions, function_name):
                    raise Exception(f"Smart contract does not have the specified function: {function_name}")
    
                the_function = getattr(w3_contract.functions, function_name)
                function_args = function_args or []
                res = the_function(*function_args).call()
                return res
    
            except Exception as err:
                #breakpoint()
                raise Exception(f"Error invoking smart contract function: {function_name}. Details: {err}. Retries: {retries}")
                #print(f"Error invoking Enforcer contract function: {function_name}")
                #traceback.print_exc()
                #return None
                retries -= 1
    


class EngineOnChainMPST(Engine, models.Model):

    RE_MESSAGE_MPST = r"^([^!?]+)(([!?])([^!?]+)(->|<-)([\w]+))$"

    running_instance = models.OneToOneField(RunningInstance, null=True, blank=True, on_delete=models.SET_NULL, verbose_name="running instance")
    blockchain_configuration = models.ForeignKey(Configuration, null=True, blank=True, on_delete=models.SET_NULL, verbose_name=_("configuration"))


    contract_enforcer = models.ManyToManyField(Contract, through="EngineHasContract", verbose_name=_("contract enforcer"), related_name="enforcer_engine_mpst")

#    curr_states = models.JSONField(default=[], verbose_name=_("current states"))
#    history = models.JSONField(default=[], verbose_name=_("history"))
#    buffer = models.JSONField(default={}, verbose_name=_("buffer"))
#    kb = models.JSONField(default=[], verbose_name=_("knowledge base"))

    execution_started = models.DateTimeField(null=True, blank=True, help_text=_("The time when the instance was started, if it was ever executed"))
    execution_ended = models.DateTimeField(null=True, blank=True, help_text=_("The time when the instance was started, if it was ever executed"))

    stats = models.JSONField(default=list)
    created_at = models.DateTimeField(null=True, blank=False, auto_now_add=True, help_text=_("The time when the engine has been created"))



    curr_states = models.JSONField(default=list, encoder=StateVarEncoder, verbose_name=_("current states"))
    history = models.JSONField(default=list, verbose_name=_("history"))
    buffer = models.JSONField(default=dict, verbose_name=_("buffer"))
    kb = models.JSONField(default=dict, verbose_name=_("knowledge base"))

    execution_started = models.DateTimeField(null=True, blank=True, help_text=_("The time when the instance was started, if it was ever executed"))
    execution_ended = models.DateTimeField(null=True, blank=True, help_text=_("The time when the instance was started, if it was ever executed"))

    created_at = models.DateTimeField(null=True, blank=False, auto_now_add=True, help_text=_("The time when the engine has been created"))

    stats = models.JSONField(default=list)

    def set_global_type(self, gt):

        self._global_type = gt
        self._local_types = {}
        self.curr_states = {}
        self.pruning_relation = {}

        for p in gt.participants:
            lt = gt.project(p)
            self._local_types[p] = lt
            self.curr_states[p] = [ lt.initial ]
            self.pruning_relation[p] = PruningRelation()


    @staticmethod
    def create_engine(ri : RunningInstance, transaction_callback = None, deploy_callback = None): 


        gt = ri.mpst.root

        e = EngineOnChainMPST()
        e._lts = gt
        e.set_global_type(gt)

        blockchain_configuration = ri.blockchain_configuration

        e.blockchain_configuration = blockchain_configuration
        e._w3 : Web3 = blockchain_configuration.get_w3()
        e._debug_log("Connected.")


        #breakpoint()
        num_sv = len(list(gt.states))
        num_transitions = len(gt.transitions)
        num_events = len(gt.messages)

        e._debug : bool = True
        e.stats = [ { "gt_num_state_variables": num_sv, "gt_num_transitions": num_transitions, "gt_num_events": num_events } ]


        # test network connection, by retrieving the network_id
        network_id = e._w3.net.version
        e._debug_log(f"Network ID: {network_id}")
        
        # test account
        #account = Account.from_key(blockchain_configuration.private_key)
        account = blockchain_configuration.get_account()
        balance = e._w3.eth.get_balance(account.address) 
        print(f"Account: {account.address} . Balance: {e.w3.from_wei(balance, 'ether')} ETH")

        #breakpoint()
        e._transaction_callback = transaction_callback
        e._deploy_callback = deploy_callback

        #if the_filter:
        #    e.set_filter(the_filter)

        e.running_instance = ri

        e.save()

        return e


    def deploy_smart_contracts(self): #, ri:RunningInstance=None):
        import hashlib

        #if not self._nfa:
        #breakpoint()
        if not self._lts:
            raise Exception("No MPST has been set for this purpose")

        if not self.blockchain_configuration:
            raise Exception("No blockchain configuration has been set. Cannot continue")
    
        #scg: SmartContractGenerator = SmartContractGenerator(self._nfa)
        scg: MPSTSmartContractGenerator = MPSTSmartContractGenerator(self._lts)
        sc : SmartContract = scg.createSmartContract()
        sc.compile(debug=self._debug)
 
        # 1. deploy the Incomp library
        sc_incomp_abi = sc.get_abi("Incomp")
        sc_incomp_bytecode = sc.get_bytecode("Incomp")
        sc_incomp_hash = Contract.get_bytecode_hash(sc_incomp_bytecode)

        #breakpoint()
        # if it does not exist, deploy a new instance
        sc_incomp = Contract.objects.filter(
                        blockchain_configuration=self.blockchain_configuration,
                        bytecode_hash=sc_incomp_hash).first()

        #breakpoint()
        if not sc_incomp:
            sc_incomp = Contract.objects.create(
                        blockchain_configuration=self.blockchain_configuration,
                        bytecode_hash=sc_incomp_hash,
                        abi=sc_incomp_abi, 
                        bytecode=sc_incomp_bytecode, 
                        label="Incomp", 
                   )
            _, incomp_stats = sc_incomp.deploy()
            self._log_stats(incomp_stats)
        else:
            print(f"********** Reuse smart contract: {sc_incomp} ...")
    
        ehc = EngineHasContract.objects.create(engine=self, contract=sc_incomp, name="__Incomp__")

  
        # 2. deploy the States library
        sc_states_abi = sc.get_abi("States")
        sc_states_bytecode = sc.get_bytecode("States")
        sc_states_hash = Contract.get_bytecode_hash(sc_states_bytecode)

        sc_states = Contract.objects.filter(
                        blockchain_configuration=self.blockchain_configuration,
                        bytecode_hash=sc_states_hash).first()
        if not sc_states:
            sc_states = Contract.objects.create(
                        blockchain_configuration=self.blockchain_configuration,
                        bytecode_hash=sc_states_hash,
                        abi=sc_states_abi, 
                        bytecode=sc_states_bytecode, 
                        label="States", 
                )
            _, states_stats = sc_states.deploy()
            self._log_stats(states_stats)
        else:
            print(f"Reusing smart contract: {sc_states} ...")

        ehc = EngineHasContract.objects.create(engine=self, contract=sc_states, name="__State__")
        print(f"States library deployed ({sc_states.contract_address}) ...")    

        # 3. deploy the Events library
        sc_events_abi = sc.get_abi("Events")
        sc_events_bytecode = sc.get_bytecode("Events")
        sc_events_hash = Contract.get_bytecode_hash(sc_events_bytecode)

        sc_events = Contract.objects.filter(
                        blockchain_configuration=self.blockchain_configuration,
                        bytecode_hash=sc_events_hash).first()

        if not sc_events:
            sc_events = Contract.objects.create(
                        blockchain_configuration=self.blockchain_configuration,
                        bytecode_hash=sc_events_hash,
                        abi=sc_events_abi, 
                        bytecode=sc_events_bytecode, 
                        label="Events", 
                )
            _, events_stats = sc_events.deploy()
            self._log_stats(events_stats)
        else:
            print(f"Reuse smart contract: {sc_events} ...")

        ehc = EngineHasContract.objects.create(engine=self, contract=sc_events, name="__Event__")


        self.curr_states = {}

        # 3. deploy all participant's enforcers
        for curr in sorted(self.lts.participants):
            sc_enforcer_abi = sc.get_abi(curr)
            sc_enforcer_bytecode = sc.get_bytecode(curr, { "Events": sc_events.contract_address, "States": sc_states.contract_address, "Incomp": sc_incomp.contract_address })
            sc_enforcer = Contract.objects.create(
                            abi=sc_enforcer_abi, 
                            bytecode=sc_enforcer_bytecode, 
                            label=curr, 
                            blockchain_configuration=self.blockchain_configuration)
    
            _, enforcer_stats = sc_enforcer.deploy()
            self._log_stats(enforcer_stats)

            ehc = EngineHasContract.objects.create(engine=self, contract=sc_enforcer, name=curr)
            print(f"Enforcer contract deployed for participant {curr} ({sc_enforcer.contract_address}) ...")    

            self.blockchain_configuration.sync()

        # 4. fetch participants' states
        for curr in sorted(self.lts.participants):
            print(f"Load {curr} states ...")
            self.curr_states[curr] = list(map(self._decode_state, sc_enforcer.invoke("getStates")))
            print(f"Loaded {curr} states: {self.curr_states[curr]} ...")

        #self.contract_nfa =sc_nfa
        #self.contract_enforcer = sc_enforcer
        #breakpoint()
        self.save()


    def attach_smart_contracts(self): #, sc_enforcer_address): #, ri=None):
        raise Exception("Not implemented yet")


    def process_input(self, precondition, event, knowledge):

        if not self.contract_enforcer:
            raise Exception(f"No enforcer contract(s) defined. Not ready for this method")


        pattern = r'([A-Za-z_0-9]+)([!?])([A-Za-z_0-9]+)(->|<-)([A-Za-z_0-9]+)'
        #parts = re.split(r'([!?])', event)

        #match = self._filter.match(parts[0], parts[1], parts[2])
        match = re.fullmatch(pattern, event)
        if not match:
            return "" #event
        try:
            #if len(parts) != 3:
            #    raise ValueError(f"Unhandled event: {event}")
            #
            #agent = self._encode_agent(parts[0])
            #action = self._encode_action(parts[1])
            #message = self._encode_message(parts[2])
            agent, action, message, _, target = match.groups()
            enc_agent = self._encode_agent(agent)
            enc_action = self._encode_action(action)
            enc_message = self._encode_message(message)
            enc_target = self._encode_agent(target)
        except Exception:
            self._debug_log(f"Symbol not recognized: {event}")
            return None
        

        #breakpoint()
        try:
            the_contract = self.contract_enforcer.get(label=agent)
            
            output_before = the_contract.invoke("getOutput")
            buffer_before = the_contract.invoke("getBuffer")
            #breakpoint()
            args = [ agent, action, target, message ]
            enc_args = [ enc_agent, enc_action, enc_target, enc_message, ]
            print(f"**> Encode ({args}) -> ({enc_args})")
            print(f"**> Invoke [{agent}] check_event({args}) - Output before: {output_before} - Buffer before: {buffer_before}")
            _, process_input_stats = the_contract.transact("check_event", enc_args)

            self._log_stats(process_input_stats)

            self.save()

            self.blockchain_configuration.sync()

            output_after = the_contract.invoke("getOutput")
            buffer_after = the_contract.invoke("getBuffer")
            print(f"**> Output after: {output_after} - Buffer after: {buffer_after}")

        except requests.exceptions.ReadTimeout:
            self._debug_log(f"Timeout estimating gas. Transaction: {transaction}",)
            return None

        except requests.exceptions.ConnectionError:
            self._debug_log(f"Connection error estimating gas. Transaction: {transaction}")
            return None

        except Contract.DoesNotExist:
            output_after = output_before # TODO was this path tested? -FS
    
        # decode every item of the tuple in the list

        
        #decode_ev = lambda ev: (self._decode_agent(ev[0]), self._decode_action(ev[1]), self._decode_agent(ev[2]), self._decode_message(ev[3]))

        events = output_after[len(output_before):]
        res = []
        action_to_direction = { "!" : "->", "?" : "<-" }

        for ev in events:
            #curr = decode_ev(curr_enc)
            initiator = self._decode_agent(ev[0])
            action = self._decode_action(ev[1])
            target = self._decode_agent(ev[2])
            label = self._decode_message(ev[3])
            direction = "->" if action == "!" else "<-"
            res.append(f"{initiator}{action}{label}{direction}{target}")
            
        return res



    def process_check(self):    
        print(f"(* Not needed for MPST *)")


    def get_curr_states(self, participant=None):
        #breakpoint()
        res = set()
        if participant:
            the_contract = self.contract_enforcer.get(label=participant)
            states_enc = the_contract.invoke("getStates")
            states_dec = list(map(self._decode_state, states_enc))
            res = set(states_dec)
        else:
            for p in self.lts.participants:
                the_contract = self.contract_enforcer.get(label=p)
                #res[p] = the_contract.invoke("getStates")
                res.update(map(self._decode_state, the_contract.invoke("getStates")))

        return sorted(res)

    def some_state_is_current(self, states, participant=None):
        #breakpoint()
        curr_states = self.get_curr_states(participant)

        return len(states.intersection(curr_states)) > 0


    def get_acceptable_events(self, participant=None):
        
        res = []
    

        curr_transitions = self.get_current_transitions(participant=participant)

        for t in curr_transitions:
            if t.is_concat:
                msgexc = t.rhs.arguments[0]
                #breakpoint()
                if msgexc.is_global:
                    res.append(msgexc.send_event)
                    res.append(msgexc.receive_event)
                else:   
                    res.append(msgexc.event)

        #breakpoint()
        return set(res)

    def get_current_transitions(self, participant=None):
        res = []
        curr_states = set(map(str, self.get_curr_states(participant=participant)))
        if not participant:
            transitions = self.get_transitions()
        else:
            transitions = self._local_types[participant].transitions

        for t in transitions:
            if len(set(t.source.states).intersection(curr_states)) > 0:
                res.append(t)

        return res
            

    def get_execution_started(self):
        return self.execution_started

    def get_execution_ended(self):
        return self.execution_ended    

    def ended(self):
        # TODO re-implement this
        print("(* EngineOnChainMPST.ended() not implemented yet *)")
        return False

 
    def _encode_state(self, value):

        assert isinstance(value, str), f"Expected string as state name. Passed: {value}"

        #if not self._nfa:
        if not self._lts:
            #raise Exception("No NFA has been set for this purpose")
            raise Exception("No LTS has been set for this purpose")

#        if isinstance(value, nfa.State):
#            value = value.id

        #return sorted(map(lambda s: s.id, self._nfa.states)).index(value)
        return sorted(map(lambda s: s.id, self._lts.states)).index(value)

    def _decode_state(self, enc):

        states = sorted(self._lts.states)
        return states[enc]

    def _encode_action(self, value):
        # this is based on the enum appearing in the template for MPST enforcers
        if value == "!":
            return 0
        elif value == "?":
            return 1
        else:
            raise ValueError(f"Unhandled action: {value}")

    def _decode_action(self, encoded):
        # this is based on the enum appearing in the template for MPST enforcers
        if encoded == 0:
            return "!"
        elif encoded == 1:
            return "?"
        else:
            raise ValueError(f"Unhandled encoded action: {encoded}")


    def _encode_agent(self, value):

        #if not self._nfa:
        if not self._lts:
            raise Exception("No NFA has been set for this purpose")

        return sorted(self._lts.participants).index(value)

    def _decode_agent(self, encoded):

        #if not self._nfa:
        if not self._lts:
            raise Exception("No NFA has been set for this purpose")

        value = sorted(self._lts.participants)[encoded]
        return value
       
    def _encode_message(self, value):

        if not self._lts:
            raise Exception("No NFA has been set for this purpose")

        return sorted(self._lts.messages).index(value)

    def _decode_message(self, encoded):

        if not self._lts:
            raise Exception("No NFA has been set for this purpose")

        return sorted(self._lts.messages)[encoded]

    def _decode_buffer_item(self, encoded):
        raise Exception("Not implemented yet!")
        #precondition, ( actor, action, message ) , knowledge = encoded
        #
        #return precondition, ( self._decode_agent(actor), self._decode_action(action), self._decode_message(message) ), knowledge




    def _log_stats(self, obj : dict):

        obj = json.loads(json.dumps(obj, cls=DjangoJSONEncoder))
        self.stats.append(obj)


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
 

    def get_buffer_items(self):
        assert self.contract_enforcer is not None
        #return list(map(self._decode_buffer_item, self.contract_enforcer.invoke("getBuffer")))
        #breakpoint()

        buffer = []
        for p in self.lts.participants:
            items = self.contract_enforcer.get(label=p).invoke("getBuffer")
            buffer.extend(items)

        #breakpoint()
        return buffer



class EngineHasContract(models.Model):

    engine = models.ForeignKey(EngineOnChainMPST, null=True, blank=False, on_delete=models.SET_NULL)
    contract = models.ForeignKey(Contract, null=True, blank=False, on_delete=models.SET_NULL)
    name = models.CharField(max_length=100, null=True, blank=False, verbose_name=_("name"))

class EngineOnChain(Engine,models.Model):

    running_instance = models.OneToOneField(RunningInstance, null=True, blank=True, on_delete=models.SET_NULL, verbose_name="running instance")
    blockchain_configuration = models.ForeignKey(Configuration, null=True, blank=True, on_delete=models.SET_NULL, verbose_name=_("configuration"))

    contract_nfa = models.OneToOneField(Contract, null=True, on_delete=models.SET_NULL, verbose_name=_("contract nfa"), related_name="nfa_engine")
    contract_enforcer = models.OneToOneField(Contract, null=True, on_delete=models.SET_NULL, verbose_name=_("contract enforcer"), related_name="enforcer_engine")

#    curr_states = models.JSONField(default=[], verbose_name=_("current states"))
#    history = models.JSONField(default=[], verbose_name=_("history"))
#    buffer = models.JSONField(default={}, verbose_name=_("buffer"))
#    kb = models.JSONField(default=[], verbose_name=_("knowledge base"))

    execution_started = models.DateTimeField(null=True, blank=True, help_text=_("The time when the instance was started, if it was ever executed"))
    execution_ended = models.DateTimeField(null=True, blank=True, help_text=_("The time when the instance was started, if it was ever executed"))

    stats = models.JSONField(default=list)
    created_at = models.DateTimeField(null=True, blank=False, auto_now_add=True, help_text=_("The time when the engine has been created"))

 

#    def __init__(self, nfa : nfa.NFA, chain_url : str, chain_id : int, wallet_address : str, private_key : str, transaction_callback = None, deploy_callback = None):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._transaction_callback = None
        self._deploy_callback = None

        self._debug : bool = True
        self._runID = uuid.uuid4()

    def __str__(self):
        return f"{self.created_at} : {self.running_instance}"

    @property
    def contract_nfa_size(self):
        return self.contract_nfa.bytecode_size if self.contract_nfa else 0

    @property
    def contract_enforcer_size(self):
        return self.contract_enforcer.bytecode_size if self.contract_enforcer else 0

    @property
    def contracts_size(self):
        return self.contract_nfa_size + self.contract_enforcer_size

    @property
    def nfa(self):
        #nfa = getattr(self, "_nfa", None)
        lts = getattr(self, "_lts", None)

        if lts is not None and not isinstance(lts, nfa.NFA):
            raise Exception(f"LTS is present but is not NFA: {lts}")

        #if not nfa:
        elif not lts:
            lts = self.running_instance.choreography.to_nfa(optimize=True)
            #self._nfa = nfa
            self._lts = lts

        #return nfa
        return lts

    @property
    def cost_wei(self):
        res = None
        if self.stats:
            res = sum([ curr["balance_before"] - curr["balance_after"] for curr in self.stats if "balance_before" in  curr and "balance_after" in curr ]) #self.stats[0]["balance_before"]

        return res

    @property
    def cost_eth(self):
        cost = self.cost_wei
        return Decimal(cost) / Decimal(10**18) if cost is not None else None

    @property
    def cost_gas(self):
        res = None

        if self.stats:
            res = sum([ curr["gas"] for curr in self.stats if "gas" in curr ])

        return res

    @property
    def overhead_build(self):
        res = None
        if self.stats:
            res = sum([ curr["build_time"] for curr in self.stats if "build_time" in curr ])

        return res

    @property
    def overhead_execution(self):
        res = None
        if self.stats:
            res = sum([ curr["execution_time"] for curr in self.stats if "execution_time" in curr ])

        return res

    @property
    def overhead_total(self):
        res = (self.overhead_build or 0) + (self.overhead_execution or 0)
        
        return res

    @staticmethod
    def create_engine(ri : RunningInstance, transaction_callback = None, deploy_callback = None, the_filter : Filter = None): #nfa : nfa.NFA, blockchain_configuration : Configuration, transaction_callback = None, deploy_callback = None):

        #breakpoint()
        nfa_start = datetime.now()
        nfa = ri.choreography.to_nfa(optimize=True)
    
        nfa_end = datetime.now()

        blockchain_configuration = ri.blockchain_configuration

        e = EngineOnChain()
        #e._nfa = nfa
        e._lts = nfa
        e.blockchain_configuration = blockchain_configuration
        e._w3 : Web3 = blockchain_configuration.get_w3()
        e._debug_log("Connected.")
        num_states = len(nfa.states)
        num_transitions = len(nfa.transitions)
        num_events = len(nfa.events)
        e.stats = [ { "nfa_build_time": float((nfa_end - nfa_start).total_seconds()), "nfa_num_states": num_states, "nfa_num_transitions": num_transitions, "nfa_num_events": num_events } ]


        # test network connection, by retrieving the network_id
        network_id = e._w3.net.version
        e._debug_log(f"Network ID: {network_id}")
        
        # test account
        #account = Account.from_key(blockchain_configuration.private_key)
        account = blockchain_configuration.get_account()
        balance = e._w3.eth.get_balance(account.address) 
        print(f"Account: {account.address} . Balance: {e.w3.from_wei(balance, 'ether')} ETH")

        #breakpoint()
        e._transaction_callback = transaction_callback
        e._deploy_callback = deploy_callback

        if the_filter:
            e.set_filter(the_filter)

        e.running_instance = ri

        e.save()

        return e


    def deploy_smart_contracts(self): #, ri:RunningInstance=None):

        #if not self._nfa:
        if not self._lts:
            raise Exception("No NFA has been set for this purpose")

        if not self.blockchain_configuration:
            raise Exception("No blockchain configuration has been set. Cannot continue")
    
        #scg: SmartContractGenerator = SmartContractGenerator(self._nfa)
        scg: SmartContractGenerator = SmartContractGenerator(self._lts)
        sc : SmartContract = scg.createSmartContract()
        sc.compile(debug=self._debug)
    
        # 0. deploy the Utils library
        sc_utils_abi = sc.get_abi("Utils")
        sc_utils_bytecode = sc.get_bytecode("Utils")
        sc_utils = Contract.objects.create(
                        abi=sc_utils_abi, 
                        bytecode=sc_utils_bytecode, 
                        label="Utils", 
                        blockchain_configuration=self.blockchain_configuration)

        _, utils_stats = sc_utils.deploy()

        self._log_stats(utils_stats)

        print(f"Utils library deployed ({sc_utils.contract_address}) ...")    

        # 1. deploy NFA contracta
        sc_nfa_abi = sc.get_abi("_NFA")
        sc_nfa_bytecode = sc.get_bytecode("_NFA", { "Utils": sc_utils.contract_address })
        sc_nfa = Contract.objects.create(
                        abi=sc_nfa_abi, 
                        bytecode=sc_nfa_bytecode, 
                        label="_NFA", 
                        blockchain_configuration=self.blockchain_configuration)

        _, nfa_stats = sc_nfa.deploy() #self.blockchain_configuration)
        self._log_stats(nfa_stats)

        self._nfa_address = sc_nfa.contract_address
        print(f"NFA contract deployed ({sc_nfa.contract_address}) ...")    

        # 2. deploy Enforcer contracta
        sc_enforcer_abi = sc.get_abi("Enforcer")
        sc_enforcer_bytecode = sc.get_bytecode("Enforcer", { "Utils": sc_utils.contract_address })
        sc_enforcer = Contract.objects.create(
                        abi=sc_enforcer_abi, 
                        bytecode=sc_enforcer_bytecode, 
                        label="Enforcer", 
                        blockchain_configuration=self.blockchain_configuration)

        _, enforcer_stats = sc_enforcer.deploy([ sc_nfa.contract_address ])
        self._log_stats(enforcer_stats)
        print(f"Enforcer contract deployed ({sc_enforcer.contract_address}) ...")    

        self.contract_nfa =sc_nfa
        self.contract_enforcer = sc_enforcer
        self.save()

    def attach_smart_contracts(self): #, sc_enforcer_address): #, ri=None):

        self._nfa_abi = self.contract_nfa.abi
        self._nfa_bytecode = self.contract_nfa.bytecode
        self._enforcer_abi = self.contract_enforcer.abi
        self._enforcer_bytecode = self.contract_enforcer.bytecode

        # query the enforcer smart contract to get the address of the nfa smart contract
        # (from blockchain)    

        self._enforcer_address = self.contract_enforcer.contract_address #sc_enforcer_address
        self._nfa_address = self.contract_nfa.contract_address

##        print(f"Fetching NFA contract address from enforcer smart contract ...")
##        self._nfa_address = self.w3.eth.contract(
##                address = self.contract_enforcer.contract_address,
##                abi = self.contract_enforcer.abi
##            ).functions.getNfaAddress().call()
##
##        assert self._nfa_address == contract.contract_nfa.contract_address, "Enforcer and NFA contracts are not linked correctly on-chain and on the database: cfr. {self._nfa_address} (blockchain) vs. {contract.contract_nfa.contract_address} (DB)"
##

    def _encode_state(self, value):

        assert isinstance(value, str), f"Expected string as state name. Passed: {value}"

        #if not self._nfa:
        if not self._lts:
            #raise Exception("No NFA has been set for this purpose")
            raise Exception("No LTS has been set for this purpose")

#        if isinstance(value, nfa.State):
#            value = value.id

        #return sorted(map(lambda s: s.id, self._nfa.states)).index(value)
        return sorted(map(lambda s: s.id, self._lts.states)).index(value)

    def _encode_action(self, value):
        
        if value == "!":
            return 1
        elif value == "?":
            return 2
        else:
            raise ValueError(f"Unhandled action: {value}")

    def _decode_action(self, encoded):

        if encoded == 1:
            return "!"
        elif encoded == 2:
            return "?"
        else:
            raise ValueError(f"Unhandled encoded action: {encoded}")


    def _encode_agent(self, value):

        #if not self._nfa:
        if not self._lts:
            raise Exception("No NFA has been set for this purpose")

        #return 1 + sorted(self._nfa.agents).index(value)
        return 1 + sorted(self._lts.agents).index(value)

    def _decode_agent(self, encoded):

        #if not self._nfa:
        if not self._lts:
            raise Exception("No NFA has been set for this purpose")

        #value = sorted(self._nfa.agents)[encoded - 1]
        value = sorted(self._lts.agents)[encoded - 1]
        return value
       
    def _encode_message(self, value):

        #if not self._nfa:
        if not self._lts:
            raise Exception("No NFA has been set for this purpose")

        #return 1 + sorted(self._nfa.messages).index(value)
        return 1 + sorted(self._lts.messages).index(value)

    def _decode_message(self, encoded):

        #if not self._nfa:
        if not self._lts:
            raise Exception("No NFA has been set for this purpose")

        #return sorted(self._nfa.messages)[encoded - 1]
        return sorted(self._lts.messages)[encoded - 1]

    def _decode_buffer_item(self, encoded):
        precondition, ( actor, action, message ) , knowledge = encoded
    
        return precondition, ( self._decode_agent(actor), self._decode_action(action), self._decode_message(message) ), knowledge

    def get_execution_started(self):
        assert self.contract_enforcer is not None
        start_time = self.contract_enforcer.invoke("getStartTime")
        return datetime.fromtimestamp(start_time)


    def get_execution_ended(self):
        assert self.contract_enforcer is not None
        end_time = self.contract_enforcer.invoke("getEndTime")

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


    def __log(self, contractAddress, gasUsed, cost, executionTime, type = None):
        if self.log_file:
            with open(self.log_file, 'a', encoding="utf-8") as f:
                    f.write(f"{self._runID};{self.chain_id};{timezone.now()};{type};{contractAddress};{gasUsed};{cost};{executionTime}\n")
                    #f.write(tabulate(self._stats, headers=["Transaction", "Contract Address", "Gas Used", "Cost (Eth)", "Execution Time (s)", ""],tablefmt="tsv"))
                    #f.write("\n")
    
    def _log_stats(self, obj : dict):

        obj = json.loads(json.dumps(obj, cls=DjangoJSONEncoder))
        self.stats.append(obj)

    @property
    def buffer(self):
        return self.get_buffer_items()

    # INTERFACE methods

    def ended(self):
        assert self.contract_nfa is not None
        return self.contract_nfa.invoke("isEnded")

    def get_all_states(self):
        assert self.contract_enforcer is not None
        return self.contract_enforcer.invoke("getNFAStates")

    def get_curr_states(self):

        assert self.contract_enforcer is not None
        return self.contract_enforcer.invoke("getNFACurrentStates")

    def get_transitions(self):
        #return self._nfa.transitions # TODO FS
        return self._lts.transitions # TODO FS

    def is_state_final(self, s):
        assert self.contract_nfa is not None
        state_encoded = self._encode_state(s)
        return self.contract_nfa.invoke("isFinal", [state_encoded])

    def is_state_initial(self, s):  

        assert self.contract_nfa is not None
        state_encoded = self._encode_state(s)
        return self.contract_nfa.invoke("isInitial", [state_encoded])

    def is_state_current(self, s):
    
        assert self.contract_nfa is not None
        state_encoded = self._encode_state(s)
        return self.contract_nfa.invoke("isCurrent", [state_encoded])

    def get_buffer_items(self):
        assert self.contract_enforcer is not None
        #return list(map(self._decode_buffer_item, self.contract_enforcer.invoke("getBuffer")))
        #breakpoint()
        return self.contract_enforcer.invoke("getBuffer")

    def get_kb(self):

        assert self.contract_enforcer is not None
        return self.contract_enforcer.invoke("getKB")


    #PROCESSORS

    def process_input(self, precondition, event, knowledge):

        # TODO this should be refactored
        if not self.contract_enforcer:
            raise Exception(f"No enforcer contract defined. Not ready for this method")

        parts = re.split(r'([!?])', event)

        match = self._filter.match(parts[0], parts[1], parts[2])
        if not match:
            return event

        try:
            if len(parts) != 3:
                raise ValueError(f"Unhandled event: {event}")

            agent = self._encode_agent(parts[0])
            action = self._encode_action(parts[1])
            message = self._encode_message(parts[2])
        except Exception:
            self._debug_log(f"Symbol not recognized: {event}")
            return None

        output_before = self.contract_enforcer.invoke("getOutput")
         
        _, process_input_stats = self.contract_enforcer.transact("process_input", [ [], agent, action, message, [] ]) # TODO empty precondition, and empty knowledge at the moment

        self._log_stats(process_input_stats)

        self.save()

        output_after = self.contract_enforcer.invoke("getOutput")
    
        return output_after[len(output_before):]
 

    def process_check(self):

        if not self.contract_enforcer:
            raise Exception(f"No enforcer contract defined. Not ready for this method")

        output_before = self.contract_enforcer.invoke("getOutput")
        out, process_check_stats = self.contract_enforcer.transact("process_check")

        self._log_stats(process_check_stats)

        self.save()

        output_after = self.contract_enforcer.invoke("getOutput")

        #return out
        return output_after[len(output_before):]
