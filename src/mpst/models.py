from django.utils.translation import gettext as _
from django.db import models
from functools import reduce
import json
from django.conf import settings
from collections import defaultdict
import copy
import logging
import nfa
import re

##
## example configuration for printing debug output of rules
##
logging.basicConfig(
    level=logging.WARNING, # logger.DEBUG
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        #logging.FileHandler("debug.log"),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger()

def get_builtin_type(name):
    if name not in __builtins__:
        raise ValueError(f"Passed name is not a builtin symbol/type: {name}")
    t = __builtins__[name] 
    if isinstance(t, type):
        return t
    raise ValueError(f"The passed name is not a builtin type: {name}")


class IsGlobalMixin:

    @property
    def is_global(self):
        return True

class IsNotGlobalMixin:
    
    @property
    def is_global(self):
        return False

class IsLocalMixin:

    @property
    def is_local(self):
        return True

class IsNotLocalMixin:

    @property
    def is_local(self):
        return False

class StateVar(IsLocalMixin, IsGlobalMixin):

    def __init__(self, identifier):
        if isinstance(identifier, str):
            self._identifier = identifier
        elif isinstance(identifier, StateVar):
            self._identifier = identifier.identifier
        else:
            raise Exception(f"Unexpected identifier type: {identifier} ({type(identifier)})")

    def __eq__(self, other):
        if isinstance(other, str):
            return self._identifier == other
        elif isinstance(other, StateVar):
            return self._identifier == other.identifier
        else:
            return False

    def __lt__(self, other):
        if isinstance(other, StateVar):
           other = other.id

        if not isinstance(other, str):
            return NotImplemented 

        return self.id < other

    def __hash__(self):
        return hash(self._identifier)

    def __contains__(self, other):
        return self.__eq__(other)

    @property
    def identifier(self):
        return self._identifier

    @property
    def id(self):
        return self.identifier

    def __str__(self):
        return self._identifier

    @property
    def participants(self):
        return set([])

    def to_json(self):

        return str(self._identifier)

    @property
    def messages(self):
        return set()

    @property
    def events(self):
        return set()

    @property
    def state_vars(self):
        return set([ self ])

    @property
    def states(self):
        return self.state_vars


def get_all_classes():
    import inspect
    import sys
    for name, obj in inspect.getmembers(sys.modules[__name__]):
        if inspect.isclass(obj):
            yield obj

def get_class(name):
    for curr in get_all_classes():
        if curr.__name__ == name:
            return curr

def get_all_subclasses(supertype):
    for curr in get_all_classes():
        if issubclass(curr, supertype):
            yield(curr)

def get_subclass(supertype, name):
    for  curr in get_all_subclasses(supertype):
        if curr.__name__ == name:
            return curr

    raise Exception(f"Subclass of {supertype} with name {name} not found")


class Composition(object):

    def __init__(self, op : str, *arguments):
        self._op = op
        self._arguments = list(arguments)

        if len(self._arguments) < 2:
            raise Exception("At least two arguments are expected for any instance of Composition")

    def __contains__(self, other):
    
        #print(f"{other} vs. {self} ...")
        if other is None:
            return False
        
        if isinstance(other, str):
            other = StateVar(other)
    
        for curr in self._arguments:
            if isinstance(curr, str) or isinstance(curr, StateVar):
                if curr == other:
                    return True
            elif isinstance(curr, Composition):
                if other in curr:
                    return True
            else:
                raise Exception(f"Unexpected containment check: {curr} : {type(curr)}")

        return False

    def __eq__(self, other):
        
        if not isinstance(other, Composition) or len(self._arguments) != len(other.arguments):
            return False

        for a,b in zip(self._arguments, other.arguments):
            if not a == b:
                return False

        return True

    def __str__(self):
        num_arguments = len(self._arguments)

        if num_arguments == 1:
            return f"{self._op} {self._arguments[0]}"
        elif num_arguments == 2:
            return f"{self._arguments[0]} {self._op} {self._arguments[1]}"
        else:
            return f"{self._op}({','.join(map(str, self._arguments))})"

    @property
    def is_local(self):
        #breakpoint()
        #print("compute recursive is_local ...")
        return all(map(lambda a: a.is_local, self._arguments))

    @property
    def is_global(self):
        #breakpoint()
        #print("compute recursive is_global ...")
        return all(map(lambda a: a.is_global, self._arguments))

    @property
    def arguments(self):
        return self._arguments

    @property
    def participants(self):
        #breakpoint()
        #return set(reduce(lambda a,b: a.participants.union(b.participants), self._arguments))
        return set(reduce(lambda a,b: a.union(b), map(lambda c: c.participants, self._arguments)))

    def to_json(self):
        return { "type": self.__class__.__name__, "op": self._op, "arguments": list(map(lambda c: c.to_json(), self._arguments)) }

    @property
    def state_vars(self):
        res = []
        for idx, curr in enumerate(self._arguments):
            if isinstance(curr, StateVar):
                res.append(curr)
            elif isinstance(curr, Composition):
                res.extend(curr.state_vars)
            elif isinstance(curr, (MsgExc, MsgSend, MsgRecv)):
                pass
            else:
                raise Exception(f"Argument type not expected (position: {idx}): {curr} ({type(curr)}")

        return set(res)

    @property
    def states(self):
        return self.state_vars

    @property
    def messages(self):
        res = []
        for idx, curr in enumerate(self._arguments):
            if isinstance(curr, StateVar):
                #res.append(curr)
                pass
            elif isinstance(curr, Composition):
                #res.extend(curr.state_vars)
                pass
            elif isinstance(curr, (MsgExc, MsgSend, MsgRecv)):
                #pass
                res.append(curr.label)
            else:
                raise Exception(f"Argument type not expected (position: {idx}): {curr} ({type(curr)}")

        return set(res)

    @property
    def events(self):
        #breakpoint()
        res = []
        for idx, curr in enumerate(self._arguments):
            if isinstance(curr, StateVar):
                pass
            elif isinstance(curr, Composition):
                pass
            elif isinstance(curr, MsgExc):
                res.append(f"!{curr.label}<>{curr.sender}")
            elif isinstance(curr, MsgSend):
                res.append(f"!{curr.label}->{curr.receiver}")
            elif isinstance(curr, MsgRecv):
                res.append(f"?{curr.label}<-{curr.sender}")
            else:
                raise Exception(f"Argument type not expected (position: {idx}): {curr} ({type(curr)}")

        return set(res)

       



    def reduce(self, pos):
        # return a reduced version of itself by removing the argument at the given position; 
        # if the original composition has only one argument, throws an exception
        # if the reduced version has only one argument, return it directly (not the original Composition instance)
        if len(self._arguments) <= 1:
            raise Exception("An instance of Composition is expected to have two or more arguments")
        elif pos >= len(self._arguments):
            raise Exception("The passed position argument is outside the list of arguments")

        if len(self._arguments) == 2:
            return self._arguments[1-pos] # just return the _other_ argument in the list
        else:
            self._arguments.pop(pos)
            return self
            

    def replace_var(self, var : StateVar, var1: StateVar):

        new_arguments = []
        for curr in self._arguments:
            if isinstance(curr, StateVar) and curr == var:
                new_arguments.append(var1)
            elif isinstance(curr, Composition):
                curr.replace_var(var, var1)
                new_arguments.append(curr)
            else:
                new_arguments.append(curr)

        self._arguments = new_arguments

    @staticmethod
    def parse(obj):

        #print(f"Parsing: {obj}")
        if not isinstance(obj, dict) or ("type" not in obj and "t" not in obj):
            raise Exception("Ill-formed representation of a composition")

        class_name = obj["type"] if "type" in obj else obj["t"]

        #breakpoint()
        #classes = get_all_subclasses(Composition)
        # TODO
        #klass = get_subclass(Composition, class_name)
        klass = get_class(class_name)
    
        if issubclass(klass, Composition):
            arguments = []
            obj_arguments = obj["arguments"] if "arguments" in obj else obj["a"] if "a" in obj else []
            for a in obj_arguments:
                if isinstance(a, str):
                    arguments.append(StateVar(a))
                else:
                    arguments.append(Composition.parse(a))
    
            return klass(*arguments)
        elif hasattr(klass, "parse"):
            parse_method = getattr(klass, "parse")
            return parse_method(obj)
        else:
            raise Exception(f"Missing parse method for representation: {obj}")

class Fork(Composition):

    def __init__(self, *arguments):
        super().__init__("|", *arguments)


class Join(Composition):

    def __init__(self, *arguments):
        super().__init__("|", *arguments)


class InternalChoice(IsLocalMixin, IsNotGlobalMixin, Composition): # in this way, the Composition.is_local/.is_global is overridden by the two mixins (that are non-recursive)
    def __init__(self, active_sender, *arguments):
        self._active_sender = active_sender
        super().__init__("(+)", *arguments)

    @property
    def active_sender(self):
        return self._active_sender


class ExternalChoice(IsLocalMixin, IsNotGlobalMixin, Composition):
    def __init__(self, active_sender, *arguments):
        self._active_sender = active_sender
        super().__init__("&", *arguments)

    @property
    def actieve_sender(self):
        return self._active_sender


class Choice(IsGlobalMixin, IsNotLocalMixin, Composition):

    def __init__(self, *arguments):
        super().__init__("+", *arguments)


class Merge(Composition):

    def __init__(self, *arguments):
        super().__init__("+", *arguments)


class MsgSend(IsLocalMixin, IsNotGlobalMixin):

    def __init__(self, sender: str, receiver: str, label: str, payload : type | list | tuple): #, continuation : StateVar):

        if isinstance(payload, (list,tuple)):
            for curr in payload:
                if not isinstance(curr, type):
                    raise Exception(f"Unexpected payload specification: expected types or collections of types. Received: {payload}")
        elif not isinstance(payload, type):
            raise Exception(f"Unexpected payload specification: expected types or collections of types. Received: {payload}")

        self._sender = sender
        self._receiver = receiver
        self._label = label
        self._payload = payload

    def __str__(self):
        payload = "N/N"

        if isinstance(self._payload, type):
            payload = self._payload.__name__
        elif isinstance(self._payload, (list, tuple)):
            payload = ",".join(map(lambda c: c.__name__, self._payload))
    
        return f"{self._sender}!{self._label}({payload})->{self._receiver}"

    def to_json(self):
        payload = ""

        if isinstance(self._payload, type):
            payload = self._payload.__name__
        elif isinstance(self._payload, (list, tuple)):
            payload = ",".join(map(lambda c: c.__name__, self._payload))

        return { "type": self.__class__.__name__, "sender": self._sender, "receiver": self._receiver, "label": self._label, "payload": payload }



    @property
    def receiver(self):
        return self._receiver

    @property
    def sender(self):
        return self._sender

 
    @property
    def label(self):
        return self._label

    @property
    def payload(self):
        return self._payload


class MsgRecv(IsLocalMixin, IsNotGlobalMixin):


    def __init__(self, receiver: str, sender: str, label: str, payload : type | list | tuple): #, continuation : StateVar):

        if isinstance(payload, (list,tuple)):
            for curr in payload:
                if not isinstance(curr, type):
                    raise Exception(f"Unexpected payload specification: expected types or collections of types. Received: {payload}")
        elif not isinstance(payload, type):
            raise Exception(f"Unexpected payload specification: expected types or collections of types. Received: {payload}")

        self._receiver = receiver
        self._sender = sender
        self._label = label
        self._payload = payload

    def __str__(self):
        payload = "N/N"

        if isinstance(self._payload, type):
            payload = self._payload.__name__
        elif isinstance(self._payload, (list, tuple)):
            payload = ",".join(map(lambda c: c.__name__, self._payload))
    
        return f"{self._receiver}?{self._label}({payload})<-{self._sender}"


    def to_json(self):
        payload = ""

        if isinstance(self._payload, type):
            payload = self._payload.__name__
        elif isinstance(self._payload, (list, tuple)):
            payload = ",".join(map(lambda c: c.__name__, self._payload))

        return { "type": self.__class__.__name__, "sender": self._sender, "receiver": self._receiver, "label": self._label, "payload": payload }


    @property
    def sender(self):
        return self._sender

    @property
    def receiver(self):
        return self._receiver

    @property
    def label(self):
        return self._label

    @property
    def payload(self):
        return self._payload



class MsgExc(IsGlobalMixin, IsNotLocalMixin):

    def __init__(self, sender: str, receiver: str, label: str, payload : type | list | tuple): #, continuation : StateVar):

        if sender == receiver:
            raise Exception(f"Sender and receiver cannot be the same. Passed: {sender}")

        if isinstance(payload, (list,tuple)):
            for curr in payload:
                if not isinstance(curr, type):
                    raise Exception(f"Unexpected payload specification: expected types or collections of types. Received: {payload}")
        elif not isinstance(payload, type):
            raise Exception(f"Unexpected payload specification: expected types or collections of types. Received: {payload}")
        self._sender = sender
        self._receiver = receiver
        self._label = label
        self._payload = payload
        #self._continuation = continuation

    def __str__(self):
        payload = "N/N"

        if isinstance(self._payload, type):
            payload = self._payload.__name__
        elif isinstance(self._payload, (list, tuple)):
            payload = ",".join(map(lambda c: c.__name__, self._payload))
    
        return f"{self._sender} -> {self._receiver} : {self._label} <{payload}>"

    @property
    def sender(self):
        return self._sender

    @property
    def receiver(self):
        return self._receiver

    @property
    def label(self):
        return self._label

    @property
    def payload(self):
        return self._payload

    @property 
    def participants(self):
        return set([self._sender, self._receiver])

    def to_json(self):
        payload = ""

        if isinstance(self._payload, type):
            payload = self._payload.__name__
        elif isinstance(self._payload, (list, tuple)):
            payload = ",".join(map(lambda c: c.__name__, self._payload))

        return { "type": self.__class__.__name__, "sender": self._sender, "receiver": self._receiver, "label": self._label, "payload": payload }

    @staticmethod
    def parse(obj):

        payload = get_builtin_type(obj["payload"]) if "payload" in obj else int
        return MsgExc(obj["sender"], obj["receiver"], obj["label"], payload)


##class LocalConcat(Composition):
##
##    def __init__(self, *args): #lhs : MsgExc, rhs):
##
##        for curr in args[:-1]:
##            if not isinstance(curr, MsgExc):
##                raise Exception(f"All but the last argument of a LocalConcat should be MsgSend or MsgRecv")
##
##        if not isinstance(args[-1], StateVar):
##            raise Exception("The last argument of a LocalConcat should be a StateVar")
##
##        super().__init__(";", *args) #[ lhs, rhs ])
##
##    def __str__(self):
##
##        return "; ".join(map(str, self._arguments))
##


class Concat(Composition):

    def __init__(self, *args): #lhs : MsgExc, rhs):

        for curr in args[:-1]:
            if not isinstance(curr, (MsgExc, MsgSend, MsgRecv)):
                raise Exception(f"All but the last argument of a Concat should be MsgExc, MsgSend, or MsgRecv")

        if not isinstance(args[-1], StateVar):
            raise Exception("The last argument of a Concat should be a StateVar")

        super().__init__(";", *args) #[ lhs, rhs ])

    def __str__(self):

        return "; ".join(map(str, self._arguments))



class End(IsGlobalMixin, IsLocalMixin):

    def __str__(self):
        return "end"

    def to_json(self):
        return "end"

    @property
    def participants(self):
        return set([])

    @property
    def state_vars(self):
        return set()

    @property
    def states(self):
        return self.state_vars

    @property
    def messages(self):
        return set()

    @property
    def events(self):
        return set()



class PruningRelation:

    def __init__(self):
        self._to_prune = {}

    def __str__(self):

        parts = []
        for state,alt in sorted(self._to_prune.items()):
            parts.append(f"{state} -> " + ",".join(map(lambda curr: str(curr), alt)))

        text = ",".join(parts)

        return "{" + text + "}"

    #@property
    #def to_prune(self):
    #    return self._to_prune

    def to_prune(self, state):
        return self._to_prune.get(state, [])

    def add(self, source, to_prune : []):
        assert len(to_prune) > 0, "Empty to_prune not accepted"

        assert source not in self._to_prune

        self._to_prune[source] = to_prune

    def remove(self, state):
        #breakpoint()
        for source1, alternatives in self._to_prune.items():
            if source1 != state:
                # remove source from states alternatives to source1
                self._to_prune[source1].remove(state)
         
        if state in self._to_prune:
            del self._to_prune[state] # remove states alternative to source

    # this method replaces the source (single state) with targets (a list of states)
    # into the pruning relation; this means that whenever 'source' appeared as an
    # alternative to some other state 'X', now the targets replace 'source' as 
    # alternatives to 'X"
    def update(self, source, targets : []):

        assert len(targets) > 0, "Empty targets not accepted"

        for X, alt in self._to_prune.items():
            if source in alt:

                #breakpoint() # check that this changes the self._to_prune dictionary
                alt.remove(source)
                alt.extend(targets)



class Transform:

    # Alice!cwin->Charlie ; Charlie?close<-Alice
    RE_MSG = "^([^!?]+)(([!?])([^!?]+)(->|<-)([\w]+))$"


    select_concat = lambda t: t.is_concat

    def __init__(self, lhs : Composition | StateVar, rhs : Composition | StateVar | End):

        self._lhs = lhs
        self._rhs = rhs

    def is_enabled(self, states : list[StateVar], event = None):

        if event is None:
            if self.is_fork or self.is_internal_choice or self.is_external_choice or self.is_concat or self.is_passthrough or self.is_end:
                return self._lhs in states
            elif self.is_join:
                lhs1, lhs2 = self._lhs.arguments
                return lhs1 in states and lhs2 in states
            elif self.is_merge:
                lhs1, lhs2 = self._lhs.arguments
                return lhs1 in states or lhs2 in states
            else:
                raise Exception(f"Cannot check whether this transform is enabled (event is None): {self}")
        else:

            match = re.match(Transform.RE_MSG, event)
            if not match:
                return False

            if self.is_concat:
                rhs1, rhs2 = self._rhs.arguments
                if self._lhs not in states:
                    return False

                #breakpoint()
                actor, event, action, label, direction, actor1 = match.groups()
                if isinstance(rhs1, MsgSend) and action == "!" and direction == "->":
                    return rhs1.sender == actor and rhs1.label == label and rhs1.receiver == actor1
                elif isinstance(rhs1, MsgRecv) and action == "?" and direction == "<-":
                    return rhs1.receiver == actor and rhs1.label == label and rhs1.sender == actor1
                else:
                    return False
            else:
                raise Exception(f"Cannot check whether this transform is enabled (task is: {task}): {self}")
    
    def apply_fork(self, states: list[StateVar], pr: PruningRelation):

        assert self.is_fork, "Transform is not of type fork"
        assert self.lhs in states, "Transform not enabled"

        rhs1, rhs2 = self.rhs.arguments
        states.remove(self.lhs)  
        if rhs1 not in states:
            states.append(rhs1)
        if rhs2 not in states:
            states.append(rhs2) 
 
        pr.update(self.lhs, [rhs1,rhs2])
 
    def apply_join(self, states: list[StateVar], pr : PruningRelation):

        assert self.is_join, "Transform is not of type join"

        lhs1, lhs2 = self.lhs.arguments

        assert lhs1 in states and lhs2 in states, "Transform not enabled"

        states.remove(lhs1)  
        states.remove(lhs2)  
        if self.rhs not in states:
            states.append(self.rhs)

        pr.update(lhs1, [self.rhs])
        pr.update(lhs2, [self.rhs])
        
    def apply_choice(self, states : list[StateVar], pr : PruningRelation):

        assert self.is_internal_choice or self.is_external_choice, "Transform is not of type internal/external choice"

        rhs1, rhs2 = self.rhs.arguments

        assert self.lhs in states, "Transform not enabled"

        states.remove(self.lhs)
        if rhs1 not in states:
            states.append(rhs1)
        if rhs2 not in states:
            states.append(rhs2)

        pr.update(self.lhs, [rhs1,rhs2]) 

        #breakpoint()
        pr.add(rhs1, list(set(pr.to_prune(self.lhs) + [ rhs2 ])))
        pr.add(rhs2, list(set(pr.to_prune(self.lhs) + [ rhs1 ])))
     
    def apply_merge(self, states : list[StateVar], pr : PruningRelation):

        assert self.is_merge, "Transform is not of type merge"
        
        lhs1, lhs2 = self.lhs.arguments

        assert lhs1 in states or lhs2 in states, "Transform not enabled"

        if lhs1 in states:
            states.remove(lhs1)
            if self.rhs not in states:
                states.append(self.rhs)
            pr.update(lhs1, [self.rhs])
        else:
            # lhs2 in states
            states.remove(lhs2)
            if self.rhs not in states:
                states.append(self.rhs)
            pr.update(lhs2, [self.rhs])
   
    
    def apply_passthrough(self, states : list[StateVar], pr : PruningRelation):

        assert self.is_passthrough, "Transform is not of type passthrough"

        assert self.lhs in states, "Transform not enabled"

        states.remove(self.lhs)
        if self.rhs not in states:
            states.append(self.rhs)

        if self.lhs != self.rhs:
            pr.update(self.source, [self.rhs]) 

    def apply_end(self, states : list[StateVar], pr : PruningRelation):
        
        assert self.is_end, "Transform is not of type end"

        states.remove(self.lhs)
        pr.remove(self.lhs)
    
    def apply_concat(self, states : list[StateVar], pr : PruningRelation, event):
        
        assert self.is_concat, "Transform is not of type Concat"

        rhs1, rhs2 = self.rhs.arguments

        states.remove(self.lhs)
        if rhs2 not in states:
            states.append(rhs2)

        # TODO check the encoding below works
        for alt in pr.to_prune(self.lhs):
            pr.remove(alt)

        pr.remove(self.lhs)

        # TODO in the future we should do something with the event ...

      
    def apply(self, states : list[StateVar], pr : PruningRelation, event=None):

        if self.is_fork:
            return self.apply_fork(states, pr)
        elif self.is_join:
            return self.apply_join(states, pr)
        elif self.is_internal_choice or self.is_external_choice:
            return self.apply_choice(states, pr)
        elif self.is_merge:
            return self.apply_merge(states, pr)
        elif self.is_passthrough:
            return self.apply_passthrough(states, pr)
        elif self.is_end:
            return self.apply_end(states, pr)
        elif self.is_concat:
            return self.apply_concat(states, pr, event)
        else:
            raise Exception(f"Don't know how to apply this transform: {self}")


    @staticmethod
    def clone(t):
        return Transform(t.lhs, t.rhs)

    @property
    def lhs(self):
        return self._lhs
    
    @property
    def source(self):
        return self.lhs

    @property
    def rhs(self):
        return self._rhs
    
    @property
    def target(self):
        return self.rhs

    def set_lhs(self, lhs : Composition | StateVar):
        self._lhs = lhs

    def set_rhs(self, rhs : Composition | StateVar | End):
        self._rhs = rhs

    def __str__(self):
        return f"{self._lhs} = {self._rhs}"

    @property
    def is_end(self):
        return isinstance(self._lhs, StateVar) and isinstance(self._rhs, End)

    @property
    def is_passthrough(self):
        return isinstance(self._lhs, StateVar) and isinstance(self._rhs, StateVar)

    @property
    def is_indirection(self):
        return self.is_passthrough

    @property
    def is_concat(self):
        return isinstance(self._lhs, StateVar) and isinstance(self._rhs, Concat)

    @property
    def is_fork(self):
        return isinstance(self._lhs, StateVar) and isinstance(self._rhs, Fork)

    @property
    def is_join(self):
        return isinstance(self._lhs, Join) and isinstance(self._rhs, StateVar)

    @property
    def is_choice(self):
        return isinstance(self._lhs, StateVar) and isinstance(self._rhs, Choice)

    @property
    def is_merge(self):
        return isinstance(self._lhs, Merge) and isinstance(self._rhs, StateVar)

    @property
    def is_internal_choice(self):
        return isinstance(self._lhs, StateVar) and isinstance(self._rhs, InternalChoice)

    @property
    def is_external_choice(self):
        return isinstance(self._lhs, StateVar) and isinstance(self._rhs, ExternalChoice)

    @property
    def participants(self):
        return self._lhs.participants.union(self._rhs.participants)

    @property
    def lhs_vars(self):
        if isinstance(self._lhs, StateVar):
            return set([ self._lhs ])
        else:
            return self._lhs.state_vars

    @property
    def rhs_vars(self):
        if isinstance(self._rhs, StateVar):
            return set([ self._rhs ])
        else:
            return self._rhs.state_vars

    @property
    def state_vars(self):
        return self.lhs_vars.union(self.rhs_vars)

    @property
    def states(self):
        return self.state_vars

    @property
    def messages(self):
        return self.lhs.messages.union(self.rhs.messages)

    @property
    def events(self):
        return self.lhs.events.union(self.rhs.events)

    def replace_var(self, var : StateVar, var1 : StateVar):

        if isinstance(self._lhs, Composition):
            self._lhs.replace_var(var, var1)
        else:
            assert isinstance(self._lhs, StateVar)
            if self._lhs == var:
                raise Exception(f"Cannot replace state variable ({var}) in the same transform defining it ({self})")

        if isinstance(self._rhs, Composition):
            self._rhs.replace_var(var, var1)
        else:
            if isinstance(self._rhs, StateVar) and self._rhs == var:
                self._rhs = var1

    def to_json(self):

        return { "type": self.__class__.__name__, "lhs": self._lhs.to_json(), "rhs": self._rhs.to_json() }


    @staticmethod
    def parse(obj):
        if "lhs" not in obj or "rhs" not in obj:
            raise Exception("Ill-formed representation of transform.")

        lhs = obj["lhs"]
        rhs = obj["rhs"]
        #_type = obj["type"]

        if isinstance(lhs, str):  
            lhs = StateVar(lhs)
        else:
            lhs = Composition.parse(lhs)

        if isinstance(rhs, str):
            rhs = StateVar(rhs)
        else:
            rhs = Composition.parse(rhs)
    
        return Transform(lhs, rhs)    
    
    @property
    def is_local(self):
        return self._lhs.is_local and self._rhs.is_local

    @property
    def is_global(self):
        return self._lhs.is_global and self._rhs.is_global



#class GlobalType:
class TypeDef(nfa.LTS):

    def __init__(self, initial : str | StateVar, transforms : list = [], debug : bool = False):

        if isinstance(initial, str):
            initial = StateVar(initial)

        self._initial = initial
        self._participants = None
        self._transforms = []

        self._logger = logging.getLogger()
        self.set_debug(debug)

        if transforms:
            for curr in transforms:
                if not isinstance(curr, Transform):
                    raise Exception(f"Expected list of transformations. Received: {transforms}")

                self._transforms.append(curr)
 
    @property
    def state_vars(self):
        res = set([])
        for t in self.transforms:
            res = res.union(t.state_vars)

        return res

    @property
    def states(self):
        return map(lambda sv: sv.id, self.state_vars)

    @property
    def messages(self):

        res = set([])
        for t in self.transforms:
            res = res.union(t.messages)

        return res

    @property
    def events(self):

        res = set([])
        for t in self.transforms:
            res = res.union(t.events)

        return res



    @property
    def logger(self):
        return self._logger

    @property
    def debug(self):
        return self._logger.level == logging.DEBUG

    def set_debug(self, debug : bool):

        if debug:
            self._logger.setLevel(logging.DEBUG)
        else:
            self._logger.setLevel(logging.WARNING)

    @property
    def initial(self):
        return self._initial

    def is_initial(self, state_name):
        return self._initial.id == state_name

    def is_final(self, state_name):
        return False # TODO this decision must be checked; do we have final state vars in MPST's Global Types?

    def set_initial(self, initial : str | StateVar):
        #breakpoint()
        if isinstance(initial, str):
            initial = StateVar(initial)

        self._initial = initial
   
    @property
    def participants(self):
        if not self._participants:
            #self._participants = set(map(lambda c: c.participants, self._transforms))
            self._participants = set(reduce(lambda a,b: a.union(b), map(lambda t: t.participants, self._transforms)))

        return self._participants

    def find_transform(self, lhs : StateVar = None, rhs : StateVar = None, such_that = None):
        if lhs is None and rhs is None:
            raise Exception("You must specify a non-null lhs or rhs StateVar to search for")

        for t in self._transforms:
            if such_that:
                if such_that(t):
                    pass
                else:
                    continue

            if lhs:
                if isinstance(t._lhs, StateVar) and t._lhs == lhs:
                    pass
                    #return t
                elif not isinstance(t._lhs, StateVar) and lhs in t._lhs.state_vars:
                    pass
                    #return t
                else:
                    continue

            if rhs:

                if isinstance(t._rhs, StateVar) and t._rhs == rhs:
                    pass
                    #return t
                elif not isinstance(t._rhs, StateVar) and rhs in t._rhs.state_vars:
                    pass
                    #return t
                else:
                    continue

            # curr transitions passed all the checks: it is the searched one
            return t


        return None

    def replace_var(self, var : StateVar, var1: StateVar):

        for t in self._transforms:
            t.replace_var(var, var1)
            if self._initial == var:
                self.set_initial(var1)

    @property
    def transforms(self):
        return self._transforms

    @property
    def transitions(self):
        return self.transforms

    def transforms_from(self, source : StateVar, label : str = None, target : StateVar = None):

        def find_matching_event(t):
            breakpoint()
            return False

        if not label:
            return self.find_transform(source, target)
        else:
            return self.find_transfrom(source, target, such_that=find_matching_event)

    def transitions_from(self, source : StateVar, label : str = None, target : StateVar = None):
        return self.transforms_from(source, label, target)

    def enabled_transforms(self, source_list):
        result = []
        for s in source_list:
            result.extend(self.transforms_from(s))

        return result

    def enabled_transitions(self, source_list):
        return self.enabled_transforms(source_list)



    ###
    ### See Active Sender computation, Fig. 22, Danielou and Yoshida, 
    ###
    def compute_senders(self, x : StateVar = None):
    
        if not x:
            x = self._initial

        t = self.find_transform(lhs=x)

        if t.is_concat:
            return set([ t.rhs.arguments[0].sender ])
        elif t.is_choice or t.is_fork:
            res = set([])
    
            for curr in t.rhs.arguments:
                res = res | self.compute_senders(curr)

            return res
        else:
            return set()
        
    def add_transform(self, t : Transform):

        if t not in self._transforms:
            self._transforms.append(t)
            if self._participants is None:
                self._participants = t.participants
            else:
                self._participants = self._participants.union(t.participants)

    def remove_transform(self, t : Transform):

        if t in self._transforms:
            self._transforms.remove(t)

            self._participants = None # this forgets the cached property value; the actual participants will be re-computed next time the participants property is accessed


    def apply_transform(self, lhs):

        if isinstance(lhs, str):
            lhs = StateVar(lhs)

        for curr in self._transforms:
            if curr.lhs == lhs:
                return curr.rhs
            elif isinstance(curr.lhs, Composition) and lhs in curr.lhs:
                return curr

        raise Exception(f"Cannot find transform having lhs = {lhs}")


    def __str__(self):

        return "def { " + "; ".join(map(lambda c: f"[{c}]", self._transforms)) + " }  in " + str(self._initial)

    def to_json(self):
        
        return { "type": self.__class__.__name__, "initial": self._initial.to_json(), "transforms": list(map(lambda c: c.to_json(), self._transforms))  } 

    def get_thread(self, state_var : str | StateVar):
        #breakpoint()
        if isinstance(state_var, str):
            state_var = StateVar(state_var)

        thread = []

        while True:
            try:
                found = next(t for t in self._transforms if t.lhs == state_var or state_var in t.lhs)
            except StopIteration:
                # no matching item found at the end of the iteration
                break

#            if not found:
#                break

            thread.append(found)
#            if not isinstance(found.rhs, Concat) or not isinstance(found.rhs.arguments[0], MsgExc): #MsgExc):
            if not found.is_concat or not isinstance(found.rhs.arguments[0], MsgExc): #MsgExc):
                # we met a branch in the rhs, thus the thread ended
                break

            # if you reach this point, we can continue following the "linear" structure of the thread
            state_var = found.rhs.arguments[-1]

        return thread
            


class MPST(models.Model):

    name = models.TextField(max_length=100, null=True, blank=True)
    resource = models.FileField(upload_to=settings.UPLOAD_ROOT)
    enabled = models.BooleanField(default=True, verbose_name=_("enabled"))
    details = models.TextField(null=True, blank=True, verbose_name=_("details"))
 

    class Meta:
    
        verbose_name = _("MPST")
        verbose_name_plural = _("MPSTs")
        unique_together = (("name",),)

    def __init__(self, *args, **kwargs):        
        super().__init__(*args, **kwargs)
        self._root = None


    def __str__(self):
        return self.name


    @property
    def root(self):

        if self._root is None:
            with open(self.resource.path, "r") as the_content:
                obj = json.load(the_content)

                if not isinstance(obj, dict) or not "type" in obj or obj["type"] != "GlobalType":
                    raise Exception("The parsed representation of MPST is ill-formed")

                if not "transforms" in obj:
                    obj["transforms"] = []
                elif not isinstance(obj["transforms"], list):
                    raise Exception("The parsed representation of MPST contains ill-formed transforms")
            
                self._root = GlobalType.parse(obj)
    
        return self._root

    @property
    def transforms(self):
        return list(map(lambda c: Transform.parse(c), self.root["transforms"]))

    @property
    def initial(self):
        return StateVar(self.root["initial"])

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self._root = None
 
    def to_rei(self):
        from rei import MPSTToRei, render_send_receive, render_receive
        exp = MPSTToRei(self, render_send_receive) #render_receive)
        #print("REI:", exp)
        return exp

    def to_nfa(self):
        from nfa import ReiToNFA
        rei = self.to_rei()
        automaton = ReiToNFA(rei)
        return automaton

class LocalType(TypeDef):

    def __init__(self, initial : str | StateVar, transforms : list = [], debug : bool = False):
        for t in transforms:
            if not t.is_local:
                raise Exception(f"Passed transform of unexpected type: {t}")

        super().__init__(initial, transforms, debug)

    def add_transform(self, t : Transform):
        if not t.is_local:
            raise Exception(f"Passed transform of unexpected type: {t}")

        return super().add_transform(t)

    def apply_transform(self, lhs):
        if not lhs.is_local:
            raise Exception(f"Passed lhs of unexpected type: {t}")

        return super().apply_transform(lhs)

    @staticmethod
    def parse(obj):
        g = LocalType(obj["initial"])  

        for t in obj["transforms"]:
            g.add_transform(Transform.parse(t))          

        return g



class GlobalType(TypeDef):

    def __init__(self, initial : str | StateVar, transforms : list = [], debug : bool = False):
        for t in transforms:
            if not t.is_global:
                raise Exception(f"Passed transform of unexpected type: {t}")

        super().__init__(initial, transforms, debug)

    def add_transform(self, t : Transform):
        if not t.is_global:
            raise Exception(f"Passed transform of unexpected type: {t}")

        return super().add_transform(t)

    def apply_transform(self, lhs):
        if not lhs.is_global:
            raise Exception(f"Passed lhs of unexpected type: {t}")

        return super().apply_transform(lhs)

    @staticmethod
    def parse(obj):
        if not "initial" in obj:
            raise ValueError("Missing initial state variable")

        g = GlobalType(obj["initial"])  

        if "transforms" in obj:
            for t in obj["transforms"]:
                g.add_transform(Transform.parse(t))          

        return g

    def compute_receivers(self, x : StateVar = None, x_set : set = None, p_set : set = None):
        # this encodes the alg. in Fig. 6

        if not x:
            x = self._initial

        if x_set is None:
            x_set = set()

        if p_set is None:
            p_set = set()

        t = self.find_transform(lhs=x)

        if not t:
            raise Exception(f"StateVar {x} not found in lhs of transforms")

        self.logger.debug(f"compute_receivers({x}, {x_set}, {p_set}) - t = {t}")

        if t.is_end:
            return set() # 5th case

        elif t.is_merge:
            x1, x2 = t.lhs.arguments
            x3 = t.rhs
            if x3 in x_set:
                return set() # 5th case
            else:
                return self.compute_receivers(x3, x_set.union([x3]), p_set) # 6th case

        elif t.is_fork or t.is_choice:
        
            x1 = t.lhs
            x2, x3 = t.rhs.arguments            

            res1 = self.compute_receivers(x2, x_set, p_set)
            res2 = self.compute_receivers(x3, x_set, p_set)
            return res1 | res2 # 4th case; return the union

        elif t.is_concat:
            x1 = t.lhs
            x2 = t.rhs.arguments[-1] # the last argument is a state var
            
            assert isinstance(x2, StateVar)
 
            p_set_1 = set(p_set)

            for m in t.rhs.arguments[:-1]: # all the arguments but the last one are MsgExc
                assert isinstance(m, MsgExc)

                p_set_1.update([ m.receiver ]) # NB duplicates are counted once in set, of course
    
            return p_set_1 | self.compute_receivers(x2, x_set, p_set_1) # 2nd, 3rd case 

        elif t.is_join:
            return self.compute_receivers(t.rhs, x_set, p_set) # 2nd case

        else:
            raise Exception(f"Case not covered: {t}")

    def simplify(self):
        # credits : Fig. 21, Appendix B.2, "Multiparty Session Types Meet Communicating Automata", Danielou and Yoshida
    
        #breakpoint()


        g1 = GlobalType(self._initial, debug=self.debug)

        for t in self._transforms:   
            g1.add_transform(Transform.clone(t))
 
       
        self.logger.debug(f"Simplify: {self}")

        dirty = True

        counter = 0
        while dirty:
    
            self.logger.debug(f"# {counter} : {g1}")
            counter = counter + 1
            dirty = False
            
            for t in g1.transforms:
                # [sub]
#                if isinstance(t.lhs, StateVar) and isinstance(t.rhs, StateVar):
                if t.is_passthrough:
                    dirty = True
#                    for t1 in g1.transforms:
#                        if t1 != t:
#                            t1.replace_var(t.lhs, t.rhs)
#                            if g1.initial == t.lhs:
#                                g1.set_initial(t.rhs)

                    
                    self.logger.debug(f"[sub.......] G,{t} => G[{t.lhs}/{t.rhs}]")
                    g1.remove_transform(t)
                    g1.replace_var(t.lhs, t.rhs)
                    

                # [trans]
#                if isinstance(t.lhs, StateVar) and isinstance(t.rhs, Concat) and isinstance(t.rhs.arguments[0], MsgExc):
                if t.is_concat and isinstance(t.rhs.arguments[0], MsgExc):
                    dirty = True
                    t_pre = str(t)
                    rhs_reduced = t.rhs.reduce(0) # remove 
                    t.set_rhs(rhs_reduced)


                    self.logger.debug(f"[trans.....] G, {t_pre} => {t}")
                    #if len(t.rhs.arguments) > 2:
                    #    t.rhs.arguments.pop(0)
                    #elif len(t.rhs.arguments) > 1:  
                    #    t.set_rhs(t.rhs.arguments[1])
                
#                if isinstance(t.lhs, StateVar) and isinstance(t.rhs, Fork):
                if t.is_fork:
                    # [par-1] or [par-2] or nothing

                    # x1 = x2 | x3 [par-1], first condition
                    #breakpoint()
                    x2, x3 = t.rhs.arguments
                    x1 = t.lhs
                    t1 = g1.find_transform(lhs=x3, such_that=lambda t: t.is_join)
                    #if t1 is None or not isinstance(t1.lhs, Join):
                    if t1 is None: # or not t1.is_join:
                        # [par-1] (swap x2 <-> x3), first condition, commutativity

                        t1 = g1.find_transform(lhs=x2, such_that=lambda t: t.is_join)
                        x2, x3 = x3, x2
                        
                    #if t1 is not None and isinstance(t1.lhs, Join):
                    if t1 is not None: # and t1.is_join:
                        # y3 | y4 = y5 [par-1], second condition
                        y3, y4 = t1.lhs.arguments
                        y5 = t1.rhs
                        if x3 == y4:
                            # [par-1], second condition, commutativity
                            y3, y4 = y4, y3
                            
                        assert x3 == y3

                        dirty = True
                        #for t2 in g1.transforms:
                        #    if t2 != t and t2 != t1:    
                        #        g1.add_transform(t2)
    

                        self.logger.debug(f"[par-1.....] G, {x1} = {x2} | {x3}, {y3} | {y4} = {y5} => G, {x1} = {x2}, {y4} = {y5}")
                        g1.add_transform(Transform(x1, x2))
                        g1.add_transform(Transform(y4, y5))
                        g1.remove_transform(t)
                        g1.remove_transform(t1)
                        
                    else:
    
                        t1 = g1.find_transform(rhs=x1, such_that=lambda t: t.is_join)
                        if t1 is not None: # and t1.is_join:
                            # [par-2] TODO not tested
                            y4, y5 = t1.lhs.arguments
                            y1 = y1.rhs
                            assert x1 == y1

                            #for t2 in g1.transforms:
                            #    if t2 != t and t2 != t1:
                            #        g1.add_transform(t2)


                            self.logger.debug(f"[par-2.....] G, {x1} = {x2} | {x3}, {y4} | {y5} = {y1} => G, {y4} = {x2}, {y5} = {x3}")

                            g1.add_transform(Transform(y4,x2))
                            g1.add_transform(Transform(y5,x3))
                            g1.remove_transform(t)
                            g1.remove_transform(t1)

                if t.is_choice:
                    # [bra-1] or [bra-2] or nothing # TODO not tested

                    x2, x3 = t.rhs.arguments
                    x1 = t.lhs

                    t1 = g1.find_transform(lhs=x2, such_that=lambda t: t.is_merge)
                    if t1 is not None: # and t1.is_merge:

                        if t1.rhs == x1:
                            # [bra-2]

                            y2,y4 = t1.lhs.arguments
                            y1 = t1.rhs

                            # ensure that x2 == y2 by swapping lhs and rhs components
                            if x2 == y2:
                                pass
                            elif x2 == y4:
                                y2, y4 = y4, y2
                            elif x3 == y2:
                                x2, x3 = x3, x2
                            elif x3 == y4:
                                x2, x3 = x3, x2
                                y2, y4 = y4, y2

                            #for t2 in g1.transforms:
                            #    if t2 != t and t2 != t1:
                            #        g1.add_transform(t2)

                            self.logger.debug(f"[bra-2.....] G, {x1} = {x2} + {x3}, {y2} + {y4} = {y1} => G, {y4} = {x3}")
                            g1.add_transform(Transform(y4, x3))
                            g1.remove_transform(t)
                            g1.remove_transform(t1)
    
                        else:
    
                            y2, y3 = t1.lhs.arguments
                            y4 = t1.rhs
    
                            if (x2 == y2 and x3 == y3) or (x2 == y3 and x3 == y2):
                                # [bra-1]
                                #for t2 in g1.transforms:
                                #    if t2 != t and t2 != t1:
                                #        g1.add_transform(t2)
    
                                self.logger.debug(f"[bra-1.....] G, {x1} = {x2} + {x3}, {y2} + {y3} = {y4} => G, {x1} = {y4}")
                                g1.add_transform(Transform(x1, y4))    
                                g1.remove_transform(t)
                                g1.remove_transform(t1)


                if t.is_merge:
                    x1,x2 = t.lhs.arguments
                    x3 = t.rhs

                    t1 = g1.find_transform(lhs=x3, such_that=lambda t: t.is_merge)
                    if t1 is not None and t1 != t: # NB t1 != t is an additional criterium I've added, double-check
                        # [merge-comm] TODO not tested
                        y3, y4 = t1.lhs.arguments
                        y5 = t1.rhs

                        if x3 == y4:
                            # [merge-comm] second condition, commutativity (swap)
                            y3, y4 = y4, y3

                        assert x3 == y3

                        self.logger.debug(f"[merge-comm] G, {x1} + {x2} = {x3}, {y3} + {y4} = {y5} => G, {x1} + {x3} = {y5}, {x2} + {y4} = {x3}")

                        g1.add_transform(Transform(Choice(x1,x3), y5))
                        g1.add_transform(Transform(Choice(x2,y4), x3))
                        g1.remove_transform(t)
                        g1.remove_transform(t1)

        self.logger.debug(f"Final: {g1}")
        return g1


    def check_well_formed(self):

        num_ends = 0
        num_initials = 0
        num_state_vars_in_lhs = {}
        num_state_vars_in_rhs = {}

        for t in self._transforms:

            if isinstance(t.lhs, Composition):      
                for a in t.lhs.arguments:
                    if isinstance(a, End):
                        raise Exception(f"End is not expected in lhs of a composition. Found: {t}")

            if isinstance(t.rhs, Composition):
                for a in t.rhs.arguments:
                    if isinstance(a, End):
                        num_ends = num_ends + 1
            elif isinstance(t.rhs, End):
                num_ends = num_ends + 1

            for v in t.lhs_vars:
                num_in_lhs = num_state_vars_in_lhs.get(v.identifier, 0)
                num_state_vars_in_lhs[v.identifier] = num_in_lhs + 1

                if v == self._initial:
                    num_initials = num_initials + 1

            for v in t.rhs_vars:
                num_in_rhs = num_state_vars_in_rhs.get(v.identifier, 0)
                num_state_vars_in_rhs[v.identifier] = num_in_rhs + 1

        # unambiguity
        for v, num_occurrences in num_state_vars_in_lhs.items():
            if num_occurrences != 1:
                raise Exception(f"State variable is ambiguous in lhs ({v}, total occurrences: {num_occurrences})")

        for v, num_occurrences in num_state_vars_in_rhs.items():
            if num_occurrences != 1:
                raise Exception(f"State variable is ambiguous in rhs ({v}, total occurrences: {num_occurrences})")

        # unique start
        if num_initials != 1:
            raise Exception(f"Non unique start for initial variable: {self._initial} (total occurrences: {num_initials})")

        # unique end
        if num_ends > 1:
            raise Exception(f"Non unique end found (total occurrences: {num_ends})")

        # thread correctness
        g1 = self.simplify()
        #if len(g1.transforms) > 1:
        #    raise Exception(f"Threads do not meet correctness criteria after simplification: mutual recursion in state variable definitions")
        if len(g1.transforms) == 0:
            raise Exception(f"Threads do not meet correctness criteria: no transforms after simplification")
        
        #elif g1.transforms[0].lhs != g1.initial:
        #    raise Exception(f"The end state is not reachable from the initial state")
        
        if num_ends == 1:
            t = g1.find_transform(lhs=g1.initial, such_that=lambda t: t.is_end)
            if not t:
                raise Exception(f"Invalid end choreography: end state is not reachable. Simplified global type: {g1}")
        else:
            # num_ends == 0, all the merges should be recursive, e.g. { x1 + x2 = x3 ; x3 + x4 = x5 ; ... ; x_n + x_n+1 = x1 }
            for t in g1.transforms:
                assert not t.is_end
                if t.is_merge:
                    assert isinstance(t.rhs, StateVar)
                    assert isinstance(t.lhs, Merge)      
                    if t.rhs not in t.lhs.state_vars:
                        raise Exception(f"Expected mutually recursive merges. Found: {t}. Simplified global type: {g1}")


    def check_well_branched(self):

        for t in self._transforms:
            if t.is_choice:
                #senders = []
                #senders = map(lambda a: self.compute_senders(a), t.rhs.arguments)
                senders = set()
                for a in t.rhs.arguments:
                    senders = senders.union(self.compute_senders(a))

#                for curr in senders[1:]:
#                    if curr != senders[0]:
#                        raise Exception(f"Senders do not match in arguments of transform: {t}. Computed senders: {senders}")
                if len(senders) == 0:
                    raise Exception(f"No senders in Choice: {t}")
                elif len(senders) > 1:
                    raise Exception(f"Too many senders in Choice: {t}. Senders: {senders}")



    def project(self, p):

        # fig. 9, Danielou and Yoshida, 2012

        p_transforms = []

        replaces = []

        for t in self._transforms:
            if t.is_end:
                t1 = Transform(StateVar(t.lhs), End())

            elif t.is_passthrough:
                t1 = Transform(StateVar(t.lhs), StateVar(t.rhs))
                replaces.append(t1)
                
            elif t.is_fork:
                lhs_sv = t.lhs
                rhs_args = map(lambda a: StateVar(a), t.rhs.arguments)
                t1 = Transform(StateVar(lhs_sv), Fork(*rhs_args))

            elif t.is_join:
                lhs_args = map(lambda a: StateVar(a), t.lhs.arguments)
                rhs_sv = t.rhs
                t1 = Transform(Join(*lhs_args), StateVar(rhs_sv))

            elif t.is_merge:
                lhs_args = map(lambda a: StateVar(a), t.lhs.arguments)
                rhs_sv = t.rhs
                t1 = Transform(Merge(*lhs_args), StateVar(rhs_sv))

            elif t.is_concat:
                rhs_messages = t.rhs.arguments[:-1]
                rhs_sv = t.rhs.arguments[-1]
                lhs_sv = t.lhs

                rhs_args = []

                for curr in rhs_messages:
                    if p == curr.sender:
                        # p is the sender, the action is to send to the curr.receiver
                        rhs_args.append(MsgSend(curr.sender, curr.receiver, curr.label, curr.payload))
                    elif p == curr.receiver:
                        # p is the receiver, the action is to receive from th ecurr.sender
                        rhs_args.append(MsgRecv(curr.receiver, curr.sender, curr.label, curr.payload))
                    else:
                        pass

                if len(rhs_args) > 0:
                    rhs_args.append(StateVar(rhs_sv))
                    t1 = Transform(StateVar(lhs_sv), Concat(*rhs_args))
                else:
                    t1 = Transform(StateVar(lhs_sv), StateVar(rhs_sv))
                    replaces.append(t1)

            elif t.is_choice:
                senders = set()
                for a in t.rhs.arguments:
                    senders = senders.union(self.compute_senders(a))

                if len(senders) == 0:
                    raise Exception(f"No senders in Choice: {t}")
                elif len(senders) > 1:
                    raise Exception(f"Too many senders in Choice: {t}. Senders: {senders}")

                active_sender = list(senders)[0] # it is just one

                #breakpoint()
                # if we reach this point, this choice is well-branched, and we can proceed
                if active_sender == p:
                    # internal choice
                    lhs_sv = t.lhs
                    rhs_args = map(lambda a: StateVar(a), t.rhs.arguments)
                    t1 = Transform(StateVar(lhs_sv), InternalChoice(active_sender, *rhs_args))
                else:
                    # external choice
                    lhs_sv = t.lhs
                    rhs_args = map(lambda a: StateVar(a), t.rhs.arguments)
                    t1 = Transform(StateVar(lhs_sv), ExternalChoice(active_sender, *rhs_args))
            else:
                print(f"Unexpected transform type: {t} ({type(t)} : {type(t.lhs)} -> {type(t.rhs)}). Skip it ...")
                continue

            p_transforms.append(t1)

        init = StateVar(self.initial) if isinstance(self.initial, str) else StateVar(self.initial.identifier)
        lt = LocalType(init, p_transforms)

        for t in replaces:
            #print(f"Replace: {t.lhs}/{t.rhs} ...")
            #breakpoint()
            lt.remove_transform(t)
            lt.replace_var(t.lhs, t.rhs)

        return lt
            

