#from distutils.log import debug
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

from engine.models import RunningInstance, Engine, EngineOnChain, EngineOffChain

class Enforcer:

    def __init__(self, engine : Engine):
        assert nfa is not None, f"Expected not-null nfa to build an enforcer"
        self._debug : bool = True
        self._onChain : bool = isinstance(engine, EngineOnChain)
        
        self._history = []  
        self._engine = engine

        self._append_history("",self._engine.get_curr_states(), self._engine.get_buffer_items())   

    @property
    def engine(self):
        return self._engine
 
    @property
    def buffer(self):
        return self._engine.buffer if self._engine else None
   
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
##        out = None
##        if (self._onChain):
##            logs = self._engine.process_input(event)
##            self._debug_log(logs[0].args.debug)
##            out = logs[0].args.messageOut
##            out = None if out == "None" else out
##        else:
##            num_states_pre = self._engine.get_num_states() #en(self._curr_states)
##
##            if self._engine.condition_rule_send(event):
##                out = self._engine.rule_send(event)
##
##            elif self._engine.condition_rule_receive_now(event):
##                    out = self._engine.rule_receive_now(event)
##
##            elif self._engine.condition_rule_receive_delayed(event):
##                    # TODO add check that the message may actually be consumed afterwards;
##                    # without this check, it does not make sense to implement the rule "Cannot receive" 
##                out = self._engine.rule_receive_delayed(event)
##            else:
##                self._debug_log("(* No matching condition *)")        
##
##            nd_factor = (self._engine.get_num_states() - num_states_pre) / num_states_pre
##            self._debug_log(f"(* Non-determism factor: {nd_factor} *)")
##

        num_states_pre = self._engine.get_num_states() #en(self._curr_states)
        out = self._engine.process_input(event)
        nd_factor = (self._engine.get_num_states() - num_states_pre) / num_states_pre
        
        self._debug_log(f"(* Non-determism factor: {nd_factor} *)")
        
        self._append_history(event, self._engine.get_curr_states(), list(map(lambda i: f"{i[0]}?{i[1]}" ,self._engine.get_buffer_items())))
        return out
        
         


    def process_check(self):
        out = None
##        if (self._onChain):
##            logs = None
##            logs = self._engine.process_check()
##            self._debug_log(logs[0].args.debug)
##            out = logs[0].args.messageOut
##            out = None if out == "None" else out
##        else:
##
##            try:
##                actor, message = self._engine._buffer_find_usable_message()
##                out = self._engine.rule_receive_buffered(actor, message)
##            except Exception:
##                pass
##        
        try:
            out = self._engine.process_check()

            self._append_history(out, self._engine.get_curr_states(), list(map(lambda i: f"{i[0]}?{i[1]}" ,self._engine.get_buffer_items())))
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
        ris = RunningInstance.objects.all()
        if len(ris) == 0:
            print("(* none *)")
        else:
            for ri in RunningInstance.objects.all():
                print(f"* {ri}")

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




##class CmdStop(UICommand):
##
##    def execute(self, *args, **kwargs):
##
##        self.ui.set_running(False)
##

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
 

class CmdLoadInstance(UICommand):
    
    def get_completions(self):
        d = {}

        for ri in RunningInstance.objects.all():
            d[str(ri.id)] = None

        #print(f"Completions: {d}")
        return d

    def execute(self, ri_id, *args, **kwargs):

        try:
            ri : RunningInstance = RunningInstance.objects.get(id=ri_id)
            self.ui._model.add_object("ri", ri)
            
        except RunningInstance.DoesNotExist as e:
            print(f"Cannot find running instance {ri_id}")
             

class CmdStop(UICommand):
    
    def execute(self, *args, **kwargs):

        ri : RunningInstance = self.ui._model.get_object("ri")

        if not ri:
            raise Exception("No running instance loaded or started, yet")

        ri.stop()
 
 
class CmdStart(UICommand):

    def execute(self, *args, **kwargs):

        c : Choreography = self.ui._model.get_object("choreography")

        if len(args) > 0:
            c = Choreography.objects.get(name=args[0])

        if not c:
            raise Exception("You must load a choreography or start a choreography")

        if not os.path.exists("log.txt"):
            with open(f'log.txt', 'w', encoding="utf-8") as f:
                f.write("Run;Blockchain;Time;Transaction;Contract Address;Gas Used;Cost;Execution Time\n")


        #regex : rei.REI = c.to_rei()
        #automaton : nfa.NFA = nfa.ReiToNFA(regex)

        onchain_url = self.ui.get_env("ONCHAIN_URL")
        onchain_chain_id = int(self.ui.get_env("ONCHAIN_CHAIN_ID"))
        onchain_address = self.ui.get_env("ONCHAIN_ADDRESS")
        onchain_private_key = self.ui.get_env("ONCHAIN_PRIVATE_KEY")

        ri : RunningInstance = RunningInstance()
        ri.choreography = c
        ri.label = c.name

        #ri._nfa = automaton
        #ri._rei = regex
        #ri._running = True

#        if onchain_url and onchain_chain_id and onchain_address and onchain_private_key:
#            ri.engine_type = RunningInstance.EngineType.ON_CHAIN
#            e = EngineOnChain(automaton, onchain_url, onchain_chain_id, onchain_address, onchain_private_key)
#        else:
#            ri.engine_type = RunningInstance.EngineType.OFF_CHAIN
#            e = EngineOffChain(automaton)
#
#        ri._enforcer = Enforcer(e)

        ri.start() # NB the start method, also saves it
        self.ui._model.add_object("ri", ri)

        print(f"Enforcer: {ri.enforcer}") 
#        self.ui._running_instances[ri.id] = ri
##        self.ui._enforcer = Enforcer(e)
##        self.ui._rei = regex
##        self.ui._nfa = automaton
##        self.ui._running = True

#        if self.ui._enforcer._onChain:
        #if ri._enforcer._onChain:
        if isinstance(ri.enforcer, EngineOnChain):
            self.ui._debug_log(f"\nGas price:  {self.ui._enforcer._engine.w3.eth.gas_price} Wei")


#        if self.ui._enforcer.ended():
        if ri.enforcer.ended():
#            self.ui._running = False
            #ri.running = False
            ri.stop()
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
            "ri": None,
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
                print("\nEvent dictionary: \n")
                for k,v in self.ui._nfa.event_dictionary.items():
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
                    

            elif args[0] == "ri":

                ri = self.ui._model.get_object("ri")
                if not ri:
                    print("N/N")
                else:
                    #breakpoint()
                    print(f"ID            : {ri.id}")
                    print(f"Choreography  : {ri.choreography}")
                    print(f"REI           : {ri.rei}")
                    print(f"Running       : {ri.running}")
                    print(f"Exec. started : {ri.execution_started or 'N/N'}")
                    print(f"Exec. ended   : {ri.execution_ended or 'N/N'}")
                    print(f"Input         : {ri.input_events}")
                    print(f"Output        : {ri.output_events}")
                    print(f"Buffer        : {ri.buffer}")

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
                print(f"{k} = {v}")

        # TODO finish below
        elif self.ui.has_env(args[0]):
            if len(args) > 1:
                self.ui.set_env(args[0], args[1])
            else:
                v = self.ui.get_env(args[0])
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
            "list"  : CmdList(self), #self.cmd_list,
            "list_instances": CmdListInstances(self), 
            "clear" : CmdClear(self),
            "rm"    : CmdRemove(self), #self.cmd_remove,
            "load"  : CmdLoad(self), #self.cmd_load,
            "load_instance": CmdLoadInstance(self),
            "start" : CmdStart(self), # self.cmd_start,
            "stop"  : CmdStop(self), #self.cmd_stop,
            "debug" : CmdDebug(self), #self.cmd_debug,
            "help"  : CmdHelp(self), #self.cmd_help,
            "dump"  : CmdDump(self), #self.cmd_dump,
            "exit"  : CmdQuit(self), #self.cmd_quit,
            "quit"  : CmdQuit(self), #self.cmd_quit
            "stats" : CmdStats(self),
            "history": CmdHistory(self),
            "save"  : CmdSave(self),
            "env"   : CmdEnv(self),
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

    def get_env(self, key):
        return self._env[key]

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

