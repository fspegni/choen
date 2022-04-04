import nfa
import traceback
import sys
import os

class Enforcer:

    def __init__(self, nfa : nfa.NFA):
        assert nfa is not None, f"Expected not-null nfa to build an enforcer"
        self._nfa = nfa
        self._buffer = {}
        self._curr_states = set([ self._nfa.initial.id ])

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

    def buffer_add(self, actor : str, message : str):
        # actor, message = str.split("?")

        actor_buffer = self._buffer.get(actor, {})
        message_counter = actor_buffer.get(message, 0)
        actor_buffer[message] = message_counter + 1
        self._buffer[actor] = actor_buffer

    def buffer_remove(self, actor : str, message : str):

        actor_buffer = self._buffer.get(actor, {})
        message_counter = actor_buffer.get(message, 0)
        assert message_counter >= 0

        if message_counter <= 0:
            raise Exception(f"No message {message} to remove for actor {actor}")
        
        actor_buffer[message] = message_counter - 1
        self._buffer[actor] = actor_buffer

    def buffer_dump(self):
        print("BUFFER:")
        for actor, actor_buffer in self._buffer.items():
            for msg, counter in actor_buffer.items():
                for i in range(counter):
                    print(f"{actor}?{msg}")

    def buffer_has_message(self, actor=None, message=None):
        if actor is not None:
            if actor not in self._buffer:
                return False
            else:
                return message is None or \
                    (message in self._buffer[actor] and self._buffer[actor][message] > 0)

        elif message is not None:
            
            for actor, actor_buffer in self._buffer.items():
                if message in actor_buffer:
                    return True
            
            return False

        else:
            raise Exception("Please, specify either an actor or a message as argument, or both")
        
    def buffer_empty(self) -> bool:
        for actor, actor_buffer in self._buffer.items():
            for msg, counter in actor_buffer.items():
                if counter > 0:
                    return False

        return True

    
    def buffer_find_usable_message(self):
        found = None

        e_closure = self._nfa.e_closure(self._curr_states)

        for actor, actor_buffer in self._buffer.items():
            for message, counter in actor_buffer.items():
                if counter > 0:
                    event = f"{actor}?{message}"
                    for s in e_closure:
                        if self._nfa.transitions_from(s, event):
                            found = (actor, message)
                            return found
                            # break
        
        #return found
        raise Exception("No usable message found")

    
    # PROCESSORS

    def process_input(self, event : str):

        out = None

        num_states_pre = len(self._curr_states)

        if "!" in event:
            # actor, message = event.split("!")
            out = self.rule_send(event)

        elif "?" in event:
            actor, message = event.split("?")

            if self.condition_rule_receive_now(event):
                out = self.rule_receive_now(event)
            else:
                # TODO add check that the message may actually be consumed afterwards;
                # without this check, it does not make sense to implement the rule "Cannot receive" 
                out = self.rule_receive_delayed(actor, message)
        
        nd_factor = (len(self._curr_states) - num_states_pre) / num_states_pre
        print(f"(* Non-determism factor: {nd_factor} *)")

        return out

    def process_check(self):

        out = ""

        try:
            actor, message = self.buffer_find_usable_message()
            out = self.rule_receive_buffered(actor, message)
        except Exception:
            pass

        return out

    # CONDITIONS below

    def condition_rule_receive_now(self, event):

        e_closure = self._nfa.e_closure(self._curr_states)

        for curr in e_closure:
            enabled_transitions = self._nfa.transitions_from(curr, event)

            if len(enabled_transitions) > 0:
                return True

        return False

    # RULES below

    def rule_send(self, event):
        return event

    def rule_receive_now(self, event):

        reached = set()
        for s in self._curr_states:

            s_reached = self._nfa.read_symbol(event, s)

            if len(s_reached) == 0:
                print(f"(* State {s} was not compatible with event {event} and has been discarded... *)")
            else:
                reached = reached.union(s_reached)
            

        self._curr_states = reached
        return event

    def rule_receive_delayed(self, actor, message):
        self.buffer_add(actor, message)
        return ""

    def rule_receive_buffered(self, actor, message):
        
        assert actor in self._buffer and message in self._buffer[actor]
        
        counter = self._buffer[actor][message]

        assert counter > 0

        event = f"{actor}?{message}"

        reached = set()
        # accepted, new_state, remaining = self._nfa.read_string(event, self._curr_state)
        for s in self._curr_states:
            s_reached = self._nfa.read_symbol(event, s)

            if len(s_reached) == 0:
                print(f"(* State {s} was not compatible with event {event} and has been discarded... *)")
            else:
                reached = reached.union(s_reached)
            # self._curr_state = new_state
        
        self.buffer_remove(actor, message)
        # self._buffer[actor][message] = counter - 1   

        nd_factor = (len(reached) - len(self._curr_states)) / len(self._curr_states)
        print(f"(* Non-determism factor: {nd_factor} *)")
        self._curr_states = reached


        return event


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
            # "load"  : self.cmd_load,
            "start" : self.cmd_start,
            "help"  : self.cmd_help,
            "dump"  : self.cmd_dump,
            "exit"  : self.cmd_quit,
            "quit"  : self.cmd_quit
        }
        self._model = Model()
        self._enforcer = None

    def prompt(self):
        userin = None
        if self._enforcer:
            userin = prompt(self.PROMPT_ENFORCER)
        else:
            userin = prompt(self.PROMPT_CLI)

        return userin

    def process_input(self, userin):
        if self._enforcer:
            return self._process_input_enforcer(userin)
        else:
            return self._process_input_cli(userin)

    def _process_input_cli(self, userin : str):

        userin_parts = userin.split(" ")
        cmd = userin_parts[0]
        cmd_args = userin_parts[1:]

        print(f"Execute: {cmd}")
        handler = self._registry.get(cmd, None)

        if handler:
            handler(*cmd_args)
        else:
            print(f"ERROR: Command not recognized: {cmd} {' ' .join(cmd_args)}")


    def _process_input_enforcer(self, userin : str):

        assert self._enforcer is not None

        if userin[0] == "/":
            return self._process_input_cli(userin[1:])
        else:
            out = self._enforcer.process_input(userin)
            if out:
                print(out)
        
            while True:
                out1 = self._enforcer.process_check()
                if out1:
                    print(out1)
                else:
                    break
            
            if self._enforcer.nfa.is_final(self._enforcer.curr_states):
                self._enforcer = None


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

            # c.name = name
            # c.resource = os.path.join(settings.MEDIA_ROOT, filename)
            # c.save()


    def cmd_load(self, name, *args, **kwargs):
        c : Choreography = Choreography.objects.get(name=name)
        self._model.add_object("choreography", c)


    def cmd_start(self, *args, **kwargs):

        c : Choreography = self._model.get_object("choreography")

        if len(args) > 0:
            c = Choreography.objects.get(name=args[0])

        if not c:
            raise Exception("You must load a choreography or start a choreography")

        nfa : nfa.NFA = c.to_nfa()

        self._enforcer = Enforcer(nfa)

    def cmd_quit(self, *args, **kwargs):
        print(f"Good bye")

    def cmd_help(self, *args, **kwargs):
        print("Available commands: ")
        print(", ".join(self._registry.keys()))

    def cmd_dump(self, *args, **kwargs):
        if self._enforcer is None:
            print("You must start the enforcer, before dumping the state")
            return

        nfa = self._enforcer.nfa
        if len(args) > 0:
            if args[0] == "curr_states":    
                print("Current states: ")
                # print(", ".join(self._enforcer._curr_states))
                for s in self._enforcer._curr_states:
                    label = str(s)
                    if nfa.is_initial(s):
                        label = f"{label} : i"
                    if nfa.is_final(s):
                        label = f"{label} : f"
                    print(label)
            elif args[0] == "transitions":
                print("Transitions: ")
                print("\n".join(map(lambda t: str(t), nfa.transitions)))
            elif args[0] == "states":
                print("States: ")
                for s in nfa.states:
                    label = str(s)
                    if nfa.is_initial(s):
                        label = f"{label} : i"
                    if nfa.is_final(s):
                        label = f"{label} : f"
                    print(label)

    def __enter__(self):
        return self

    def __exit__(self, *args, **kwargs):
        self.cmd_quit()


def cli(*args, **kwargs):

    with UI() as ui:

        while True:
            try:
                userin = ui.prompt()
                ui.process_input(userin)
            except (EOFError, KeyboardInterrupt):
                break
            except Exception as e:
                traceback.print_exc()

