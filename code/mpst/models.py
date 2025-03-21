from django.utils.translation import gettext as _
from django.db import models
from functools import reduce
import json
from django.conf import settings
from collections import defaultdict



class StateVar:

    def __init__(self, identifier : str):
        self._identifier = identifier

    def __eq__(self, other):
        if isinstance(other, str):
            return self._identifier == other
        elif isinstance(other, StateVar):
            return self._identifier == other.identifier
        else:
            return False

    @property
    def identifier(self):
        return self._identifier

    def __str__(self):
        return self._identifier

    @property
    def participants(self):
        return set([])

    def to_json(self):

        return str(self._identifier)


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
        self._arguments = arguments

    def __contains__(self, other):
    
        print(f"{other} vs. {self} ...")
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
    def arguments(self):
        return self._arguments

    @property
    def participants(self):
        #breakpoint()
        #return set(reduce(lambda a,b: a.participants.union(b.participants), self._arguments))
        return set(reduce(lambda a,b: a.union(b), map(lambda c: c.participants, self._arguments)))

    def to_json(self):
        return { "type": self.__class__.__name__, "op": self._op, "arguments": list(map(lambda c: c.to_json(), self._arguments)) }

    @staticmethod
    def parse(obj):

        #print(f"Parsing: {obj}")
        if not isinstance(obj, dict) or "type" not in obj:
            raise Exception("Ill-formed representation of a composition")

        class_name = obj["type"]

        #breakpoint()
        #classes = get_all_subclasses(Composition)
        # TODO
        #klass = get_subclass(Composition, class_name)
        klass = get_class(class_name)
    
        if issubclass(klass, Composition):
            arguments = []
            for a in obj["arguments"]:
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


class Choice(Composition):

    def __init__(self, *arguments):
        super().__init__("+", *arguments)


class Merge(Composition):

    def __init__(self, *arguments):
        super().__init__("+", *arguments)


class MsgExc:

    def __init__(self, sender: str, receiver: str, label: str, payload : type | list | tuple): #, continuation : StateVar):

        if sender == receiver:
            raise Exception("Sender and receiver cannot be the same. Passed: {sender}")

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

        payload = int # TODO
        return MsgExc(obj["sender"], obj["receiver"], obj["label"], payload)

class Concat(Composition):

    def __init__(self, *args): #lhs : MsgExc, rhs):
        super().__init__(";", *args) #[ lhs, rhs ])

    def __str__(self):

        return "; ".join(map(str, self._arguments))


class End:

    def __str__(self):
        return "end"

    def to_json(self):
        return "end"

    @property
    def participants(self):
        return set([])


class Transform:

    def __init__(self, lhs : Composition | StateVar, rhs : Composition | StateVar | End):

        self._lhs = lhs
        self._rhs = rhs

    @property
    def lhs(self):
        return self._lhs

    @property
    def rhs(self):
        return self._rhs

    def __str__(self):
        return f"{self._lhs} = {self._rhs}"

    @property
    def participants(self):
        return self._lhs.participants.union(self._rhs.participants)


    def to_json(self):

        return { "type": self.__class__.__name__, "lhs": self._lhs.to_json(), "rhs": self._rhs.to_json() }


    @staticmethod
    def parse(obj):
        if "type" not in obj or obj["type"] != "Transform" or "lhs" not in obj or "rhs" not in obj:
            raise Exception("Ill-formed representation of transform.")

        lhs = obj["lhs"]
        rhs = obj["rhs"]
        _type = obj["type"]

        if isinstance(lhs, str):  
            lhs = StateVar(lhs)
        else:
            lhs = Composition.parse(lhs)

        if isinstance(rhs, str):
            rhs = StateVar(rhs)
        else:
            rhs = Composition.parse(rhs)
    
        return Transform(lhs, rhs)    
    

class GlobalType:

    def __init__(self, initial : str | StateVar, transforms : list = []):

        if isinstance(initial, str):
            initial = StateVar(initial)

        self._initial = initial
        self._participants = None

        if transforms:
            for curr in transforms:
                if not isinstance(curr, Transform):
                    raise Exception(f"Expected list of transformations. Received: {transforms}")
            
        self._transforms = transforms
    
    @property
    def participants(self):
        if not self._participants:
            #self._participants = set(map(lambda c: c.participants, self._transforms))
            self._participants = set(reduce(lambda a,b: a.union(b), map(lambda t: t.participants, self._transforms)))

        return self._participants

    @property
    def transforms(self):
        return self._transforms

    def add_transform(self, t : Transform):
        self._transforms.append(t)
        self._participants = self._participants.union(t.participants)

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

    @staticmethod
    def parse(obj):
        g = GlobalType(obj["initial"]) 

        for t in obj["transforms"]:
            g.add_transform(Transform.parse(t))          

        return g

    def get_thread(self, state_var : str | StateVar):
        #breakpoint()
        if isinstance(state_var, str):
            state_var = StateVar(state_var)

        thread = []

        while True:
            try:
                found = next(t for t in self._transforms if t.lhs == state_var)
            except StopIteration:
                # no matching item found at the end of the iteration
                break

#            if not found:
#                break

            thread.append(found)
            if not isinstance(found.rhs, Concat) or not isinstance(found.rhs.arguments[0], MsgExc): #MsgExc):
                # we met a branch in the rhs, thus the thread ended
                break

            # if you reach this point, we can continue following the "linear" structure of the thread
            state_var = found.rhs.arguments[-1]


        return thread
            


class MPST(models.Model):

    name = models.TextField(max_length=100, null=True, blank=True)
    resource = models.FileField(upload_to=settings.UPLOAD_ROOT)

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
