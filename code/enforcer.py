import nfa
import traceback
import sys
import os
import re
from django.core.files import File
from pathlib import Path
import prompt_toolkit
from prompt_toolkit.history import FileHistory
from prompt_toolkit.completion import NestedCompleter

class Engine:

    def __init__(self, nfa : nfa.NFA):

        assert nfa is not None, f"Expected not-null nfa to build an enforcer engine"

        self._debug : bool = True
        self._nfa = nfa

    @property
    def nfa(self):
        return self._nfa


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

    def __init__(self, nfa : nfa.NFA, chain_url : str, chain_id : str, contract_address : str, private_key : str):

        super().__init__(nfa)
        self._chain_url = chain_url 
        self._chain_id = chain_id
        self._contract_address = contract_address
        self._private_key = private_key


class Enforcer:

#    def __init__(self, nfa : nfa.NFA):
    def __init__(self, engine : Engine):
        assert nfa is not None, f"Expected not-null nfa to build an enforcer"
        self._debug : bool = True

#        self._engine = EngineOffChain(nfa)
        self._engine = engine


    @property
    def engine(self):
        return self._engine

    # DEBUG LOG

    def set_debug(self, debug: bool):
        self._debug = debug


    def _debug_log(self, text):
        if self._debug:
            print(text)


    def ended(self):
        return self._engine.ended()


    # PROCESSORS

    def process_input(self, event): #event_stream : str):
        out = None
        num_states_pre = self._engine.get_num_states() 

        if self._engine.condition_rule_send(event):
            out = self._engine.rule_send(event)

        elif self._engine.condition_rule_receive_now(event):
                out = self._engine.rule_receive_now(event)

        elif self._engine.condition_rule_receive_delayed(event):
                # TODO add check that the message may actually be consumed some time in the future;
                # without this check, it does not make sense to implement the rule "Cannot receive" 
            out = self._engine.rule_receive_delayed(event)
        else:
            self._debug_log("(* No matching condition *)")        

        nd_factor = (self._engine.get_num_states() - num_states_pre) / num_states_pre
        self._debug_log(f"(* Non-determism factor: {nd_factor} *)")

        return out


    def process_check(self):

        out = ""
#        print("in process_check ...")

        try:
            actor, message = self._engine._buffer_find_usable_message()
            out = self._engine.rule_receive_buffered(actor, message)
        except Enforcer.NoMessageFound:
            pass

        return out

    class NoMessageFound(Exception):
        pass



from enforcer import *
from bpmn_parser.models import *


#from prompt_toolkit import prompt

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
        print(", ".join(self.ui._registry.keys()))


class CmdList(UICommand):

    def execute(self, *args, **kwargs):

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




class CmdStop(UICommand):

    def execute(self, *args, **kwargs):

        self.ui.set_running(False)


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

class CmdLoad(UICommand):

    def get_completions(self):
 
        d = {}
        for c in Choreography.objects.all():
            d[c.name] = None
        return d
   
    def execute(self, name, *args, **kwargs):
        try:
            c : Choreography = Choreography.objects.get(name=name)
            self.ui._model.add_object("choreography", c)
            print(f"Choreography '{name}' loaded ...")
        except Choreography.DoesNotExist as e:
            if os.path.exists(name):
                cho_name = os.path.basename(name).rsplit(".",1)[0]
                attribs = {
                    "name": cho_name,
                    "resource": File(open(name)),
                }
                c, created = Choreography.objects.get_or_create(name=name, defaults=attribs)
                self.ui._model.add_object("choreography", c)
                if created:
                    print(f"Choreography {cho_name} imported and loaded ...")
                else:
                    print(f"Choreography {cho_name} already exists and has been loaded ...")
            else:
                print(f"Cannot find choreography {name}")
 
               
class CmdStart(UICommand):

    def execute(self, *args, **kwargs):

        c : Choreography = self.ui._model.get_object("choreography")

        if len(args) > 0:
            c = Choreography.objects.get(name=args[0])

        if not c:
            raise Exception("You must load a choreography or start a choreography")

        regex : rei.REI = c.to_rei()
        automaton : nfa.NFA = nfa.ReiToNFA(regex)

#        self.ui._enforcer = Enforcer(automaton)
        onchain_url = self.ui.get_env("ONCHAIN_URL")
        onchain_id = self.ui.get_env("ONCHAIN_ID")
        onchain_address = self.ui.get_env("ONCHAIN_ADDRESS")
        onchain_key = self.ui.get_env("ONCHAIN_KEY")

        if onchain_url and onchain_id and onchain_address and onchain_key:
            e = EngineOnChain(automaton, onchain_url, onchain_id, onchain_address, onchain_key)
        else:
            e = EngineOffChain(automaton)

        self.ui._enforcer = Enforcer(e)
        self.ui._rei = regex
        self.ui._nfa = automaton
        self.ui._running = True

        if self.ui._enforcer.ended():
            self.ui._running = False
            self.ui._debug_log("(* Ended *)")


class CmdDump(UICommand):

    def get_completions(self):
        d = {
            "curr_states": None,
            "transitions": None,
            "states": None,
            "rei": None,
            "nfa": None,
            "buffer": None,
        }

        return d

    def execute(self, *args, **kwargs):
        if self.ui._enforcer is None:
            print("You must start the enforcer, before dumping the state")
            return

        if len(args) == 0:
            print("Please specify an argument: dump <curr_states|states|transitions|buffer|rei>")
        else:
            if args[0] == "curr_states":    
                print("\nCurrent states: \n")
                for s in self.ui._enforcer.engine.get_curr_states():
                    label = str(s)
                    if self.ui._enforcer.engine.is_state_initial(s):
                        label = f"{label} : i"
                    if self.ui._enforcer.engine.is_state_final(s):
                        label = f"{label} : f"
                    print(label)
                

            elif args[0] == "transitions":
                print("\nTransitions (*=enabled): \n")
                for t in self.ui._enforcer.engine.get_transitions():

                    t_repr = str(t)
                    if self.ui._enforcer.engine.is_state_current(t.source):
                        t_repr = f" * {t_repr}"
                    else:
                        t_repr = f"   {t_repr}"

                    print(t_repr)

            elif args[0] == "states":
                print("\nStates (*=current, i=initial, f=final) : \n")
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
                for actor,message in self.ui._enforcer.engine.get_buffer_items():
                    msg = f"{actor}?{message}"

                    print(msg)
            
            elif args[0] == "rei":
                print("\nREI: \n")
                print(self.ui._rei)

            elif args[0] == "nfa":
                print("\nNFA: \n")
                g = self.ui._nfa.to_dot()   
                print(g)


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


class CmdOnChain(UICommand):

    name = "onchain"

    def get_completions(self):
        return {
            "url": None,
            "chain_id": None,
            "address": None,
            "private_key": None,
        }

    def execute(self, *args, **kwargs):

        n_args = len(args)
        
        if n_args == 0:
#            print(f"Please, specify an argument: {self.get_completions().keys()}")
            for k,v in self.ui.env:
                if k.startswith("ONCHAIN_"):
                    print(f"{k} = {v}")

        # TODO finish below
        elif args[0] == "url":
            self.ui.set_env("ONCHAIN_URL", args[1])
        elif args[0] == "chain_id":
            self.ui.set_env("ONCHAIN_ID", args[1])
        elif args[0] == "address":
            self.ui.set_env("ONCHAIN_ADDRESS", args[1])
        elif args[0] == "private_key":
            self.ui.set_env("ONCHAIN_KEY", args[1])
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
            "list"  : CmdList(self), #self.cmd_list,
            "clear" : CmdClear(self),
            "rm"    : CmdRemove(self), #self.cmd_remove,
            "load"  : CmdLoad(self), #self.cmd_load,
            "start" : CmdStart(self), # self.cmd_start,
            "stop"  : CmdStop(self), #self.cmd_stop,
            "debug" : CmdDebug(self), #self.cmd_debug,
            "help"  : CmdHelp(self), #self.cmd_help,
            "dump"  : CmdDump(self), #self.cmd_dump,
            "exit"  : CmdQuit(self), #self.cmd_quit,
            "quit"  : CmdQuit(self), #self.cmd_quit
            "save"  : CmdSave(self),
            "onchain": CmdOnChain(self),
        }
        self._model = Model()
        self._enforcer = None
        self._running = False
        self._rei = None
        self._nfa = None
        self._debug = True
        self._env = {
            "ONCHAIN_URL": "",
            "ONCHAIN_ID": "",
            "ONCHAIN_ADDRESS": "",
            "ONCHAIN_KEY": "",
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
    def env(self):
        return self._env.items()

    def get_env(self, key):
        return self._env[key]

    def set_env(self, key, value):
        self._env[key] = value

    def has_env(self, key):
        return key in self._env

    def set_running(self, v : bool):
        self._running = v


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

        iscan = nfa.InputScanner(event_stream)

        while not iscan.eof:        
            event = iscan.scan_input()
            out = self._enforcer.process_input(event)
        
            if out:
                print(out)
            
#            print("in consume events, before process_check ...")
            while True:
                out1 = self._enforcer.process_check()
                if out1:
                    print(out1)
                else:
                    break                   
            
        if self._enforcer.ended():
            self._debug_log("(* Ended *)")       
#            self._enforcer = None
#            self._rei = None
            self._running = False


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

