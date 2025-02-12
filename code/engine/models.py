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


class RunningInstance(models.Model):

    class EngineType(models.IntegerChoices):
        OFF_CHAIN = 0
        ON_CHAIN = 1

    engine_type = models.IntegerField(choices=EngineType.choices, default=EngineType.OFF_CHAIN, help_text=_("the on-chain engine uses the distributed ledger, while the off-chain engine uses only local data structures (mostly for testing purposes)"))

    blockchain_configuration = models.ForeignKey(Configuration, null=True, blank=True, on_delete=models.SET_NULL, verbose_name=_("configuration"))

    label = models.CharField(max_length=500, null=True, blank=True)
    choreography = models.ForeignKey(Choreography, null=False, blank=False, on_delete=models.DO_NOTHING)
    running = models.BooleanField(default=False)
#    enforcer = PickledObjectField(blank=True, null=True) 
    execution_started = models.DateTimeField(null=True, blank=True, help_text=_("The time when the instance was started, if it was ever executed"))
    execution_ended = models.DateTimeField(null=True, blank=True, help_text=_("The time when the instance was started, if it was ever executed"))

    input_events = models.TextField(null=True, blank=True)
    output_events = models.TextField(null=True, blank=True)


    class Meta:
        verbose_name = _("running instance")
        verbose_name_plural = _("running instances")


    @property
    def enforcer(self):
        if not self._enforcer:
            print("Setting an enforcer ...")
            self._set_enforcer()

        return self._enforcer

    @property
    def configuration(self):
        # TODO rename field: blockchain_configuration -> configuration
        return self.blockchain_configuration

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
        engine_type = "on-chain" if self.engine_type == self.EngineType.ON_CHAIN else "off-chain"
        if self.label:
            return f"{self.label}/{self.pk} ({engine_type})"
        else:
            return f"{self.pk} ({engine_type})"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._enforcer = None
        self._rei = None

    def _set_enforcer(self):
        from enforcer import Enforcer

        if not self.choreography:
            raise Exception("Cannot set enforcer if a choreography is not attached to the current running instance")

        automaton = self.choreography.to_nfa()
        if self.engine_type == self.EngineType.OFF_CHAIN:
            engine = EngineOffChain(automaton)    
        else:

            def handle_transactions(tx_hash, tx_receipt):

                #breakpoint()
        
                t = Transaction()
                t.tx_hash = tx_hash.hex()
                t.block_hash = tx_receipt["blockHash"].hex()  
                t.running_instance = self
                t.initiator_address = tx_receipt["from"]
                t.gas_used = tx_receipt["gasUsed"]
                t.contract_address = tx_receipt["contractAddress"]
                t.block_number = tx_receipt["blockNumber"]
                t.save()
       
            #breakpoint()
            engine = EngineOnChain(automaton, self.configuration.url, int(self.configuration.chain_id), self.configuration.address, self.configuration.private_key, handle_transactions)

            c_nfa = Contract.objects.filter(running_instance=self, label="nfa")
            c_enforcer = Contract.objects.filter(running_instance=self, label="enforcer")

            #breakpoint()

            if len(c_nfa) > 0 and len(c_enforcer) > 0:
                engine.load_smart_contracts(c_nfa[0].contract_address, c_nfa[0].abi, c_enforcer[0].contract_address, c_enforcer[0].abi)
            else:
                engine.deploy_smart_contracts()    
                Contract.objects.create(label="nfa", running_instance=self, contract_address=engine.nfa_address, abi=engine.nfa_abi, bytecode=engine.nfa_bytecode)           
                Contract.objects.create(label="enforcer", running_instance=self, contract_address=engine.enforcer_address, abi=engine.enforcer_abi, bytecode=engine.enforcer_bytecode)           

        self._enforcer = Enforcer(engine)
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
        if not self.input_events:
            self.input_events = new_input.strip()
        else:
            self.input_events = self.input_events + " " + new_input.strip()
        self.save()

    def append_output(self, new_output):
        if not self.output_events:
            self.output_events = new_output.strip()
        else:
            self.output_events = self.output_events + " " + new_output.strip()
        self.save()

    def start(self):

        if self.execution_ended:
            raise Exception("Cannot start the running instance: it has already been executed")
        self.running = True
        self.execution_started = timezone.now()

        self.save() # FS it was in the if-else branches, it has been here (refactoring)

        #breakpoint()

        if self.engine_type == self.EngineType.ON_CHAIN and self._enforcer:
    
            print(f"WARNING: ON_CHAIN engine type detected; not saved on database (on start)...")
            old_engine = self.enforcer.engine
            #self.enforcer.engine = None
            self.enforcer.set_engine(None)
            #self.save()
            #self.enforcer.engine = old_engine
            self.enforcer.set_engine(old_engine)
        #else:
        #    self.save()

    def stop(self):
        if not self.running:
            raise Exception("Cannot stop the running instance: it has not been started")
    
        if self.execution_ended:
            raise Exception("Cannot stop the running instance: its execution has been stopped")

        self.execution_ended = timezone.now()
        self.running = False
        self.save()


class Engine:

    def __init__(self, nfa : nfa.NFA):

        assert nfa is not None, f"Expected not-null nfa to build an enforcer engine"

        self._debug : bool = True
        self._nfa = nfa
        self._history = []

    @property
    def nfa(self):
        return self._nfa

    @property
    def history(self):
        return self._history

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
        super().__init__(nfa)
#        self._nfa : nfa.NFA = nfa
        self._buffer = {}
        self._curr_states = self._nfa.e_closure(set([ self._nfa.initial.id ]))
        self._debug : bool = True
        self._stats = [] 
 
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

    def __init__(self, nfa : nfa.NFA, chain_url : str, chain_id : int, wallet_address : str, private_key : str, transaction_callback = None, deploy_callback = None):

        super().__init__(nfa)

        assert wallet_address is not None, "You must configure your wallet address before continuing"
        assert private_key is not None, "You must configure your wallet private key before continuing"
        assert chain_url is not None, "You must configure your blockchain URL before continuing"
        assert chain_id is not None, "You must configure your blockchain chain ID before continuing"

        self._chain_url = chain_url 
        self._chain_id = chain_id
        self._wallet_address = wallet_address
        self._private_key = private_key

        self._debug : bool = True
        self._runID = uuid.uuid4()

        self._debug_log(f"\nConnecting to {self._chain_url} ...")
        self._w3 : Web3 = Web3(Web3.HTTPProvider(self._chain_url, request_kwargs={'timeout': 300}))
        self._debug_log("Connected.")

        # test network connection, by retrieving the network_id
        network_id = self._w3.net.version
        self._debug_log(f"Network ID: {network_id}")
        
        # test account
        account = Account.from_key(self._private_key)
        balance = self._w3.eth.get_balance(account.address) 
        print(f"Account: {account.address}. Balance: {self.w3.from_wei(balance, 'ether')} ETH")
        self._stats = []

        #breakpoint()
        self._transaction_callback = transaction_callback
        self._deploy_callback = deploy_callback


    def load_smart_contracts(self, nfa_address, nfa_abi, enforcer_address, enforcer_abi):

        self._nfa_abi = nfa_abi
        self._nfa_address = nfa_address
        self._enforcer_abi = enforcer_abi
        self._enforcer_address = enforcer_address


    def deploy_smart_contracts(self):

        scg: SmartContractGenerator = SmartContractGenerator(self._nfa)
        compiled_sol = scg.createSmartContract().compile(self._debug)
        
        self._nfa_abi, self._nfa_bytecode = self.__get_abi_and_bytecode(compiled_sol, "NFA")
        self._enforcer_abi, self._enforcer_bytecode = self.__get_abi_and_bytecode(compiled_sol, "Enforcer")

        self._nfa_address = self.deployContractNFA(self._nfa_abi, self._nfa_bytecode)
        self._enforcer_address = self.deployContractEnforcer(self._enforcer_abi, self._enforcer_bytecode, self._nfa_address)


    @property
    def w3(self) -> Web3:
        return self._w3
    
    @property
    def chain_id(self) -> int:
        return self._chain_id

    @property
    def address(self) -> str:
        return self._wallet_address

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
                f.write(f"{self._runID};{self._chain_id};{datetime.now()};{type};{contractAddress};{gasUsed};{cost};{executionTime}\n")
                #f.write(tabulate(self._stats, headers=["Transaction", "Contract Address", "Gas Used", "Cost (Eth)", "Execution Time (s)", ""],tablefmt="tsv"))
                #f.write("\n")
    
    def __add_statistics(self, contractAddress, gasUsed, cost, executionTime, type = None):
        self._stats.append([type, contractAddress, gasUsed, cost, executionTime])
    
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
        nonce =  self.w3.eth.get_transaction_count(self.address)

        start_time = time.time()
        # build transaction
        if (address == None):
#            transaction = contract.constructor().buildTransaction(
            transaction = contract.constructor().build_transaction(
            {
                "chainId": self.chain_id,
                "gasPrice": self.w3.eth.gas_price,
                "from": self.address,
                "nonce": nonce,
            }
        )
        else:
#            transaction = contract.constructor(address).buildTransaction(
            transaction = contract.constructor(address).build_transaction(
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
        self.__add_statistics(tx_receipt.contractAddress ,tx_receipt.gasUsed, round(self.w3.from_wei(tx_receipt.gasUsed * self._w3.eth.gas_price, 'ether'),2), round(execution_time,3), f"Contract Creation")
        self.__log(tx_receipt.contractAddress ,tx_receipt.gasUsed, round(self.w3.from_wei(tx_receipt.gasUsed * self._w3.eth.gas_price, 'ether'),2), round(execution_time,3),f"Contract Creation")
        self._debug_log(f"Done! Contract deployed to {tx_receipt.contractAddress}\n")
        return tx_receipt.contractAddress


    def deployContractNFA(self, abi, bytecode):
        return self.__deployContract("NFA", abi, bytecode)
    
    def deployContractEnforcer(self, abi, bytecode, nfa_address : str):
        return self.__deployContract("Enforcer", abi, bytecode, nfa_address)


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
            ).functions.isCurrent(s).call() # TODO FS

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
        nonce = self.w3.eth.get_transaction_count(self.address)
        start_time = time.time()
#        transaction = enforcer.functions.process_input(event).buildTransaction({
        transaction = enforcer.functions.process_input(event).build_transaction({
                        "chainId": self.chain_id,
                        "from": self.address,
                        "gasPrice": self.w3.eth.gas_price,
                        "nonce": nonce
                    })
        build_time = time.time() - start_time
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
        nonce = self.w3.eth.get_transaction_count(self.address)
        start_time = time.time()
#        transaction = enforcer.functions.process_check().buildTransaction({
        transaction = enforcer.functions.process_check().build_transaction({
                        "chainId": self.chain_id,
                        "from": self.address,
                        "gasPrice": self.w3.eth.gas_price,
                        "nonce": nonce
                    })
        build_time = time.time() - start_time
        tx_receipt = self.__sendTransaction(transaction)
        execution_time = time.time() - start_time
        self.__add_statistics(tx_receipt.contractAddress ,tx_receipt.gasUsed, self.w3.from_wei(tx_receipt.gasUsed * self._w3.eth.gas_price, 'ether'), round(execution_time,3), f"Process check")
        self.__log(tx_receipt.contractAddress ,tx_receipt.gasUsed, self.w3.from_wei(tx_receipt.gasUsed * self._w3.eth.gas_price, 'ether'), round(execution_time,3), f"Process check")
        receipt = enforcer.events.outputEvent().process_receipt(tx_receipt)

        self._debug_log(logs[0].args.debug)
        out = logs[0].args.messageOut
        out = None if out == "None" else out

        return out

class Contract(models.Model):

    contract_address =models.CharField(max_length=100, null=True, blank=False, verbose_name=_("contract address"))
    running_instance = models.ForeignKey(RunningInstance, null=True, blank=False, on_delete=models.SET_NULL, verbose_name=_("running instance"))
    label = models.CharField(max_length=100, verbose_name=_("label"))
    abi = models.JSONField(null=True, blank=False, verbose_name=_("abi"))
    bytecode = models.TextField(null=True, blank=False, verbose_name=_("bytecode"))
   

    class Meta:
        verbose_name = _("contract")
        verbose_name_plural = _("contracts")
        unique_together = (("contract_address",), ("label", "running_instance"))



class Transaction(models.Model):

    tx_hash = models.CharField(max_length=100, null=True, blank=False, verbose_name=_("hash"))
    block_hash = models.CharField(max_length=100, null=True, blank=False, verbose_name=_("block hash"))
    running_instance = models.ForeignKey(RunningInstance, null=True, blank=False, on_delete=models.SET_NULL, verbose_name=_("running instance"))

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
