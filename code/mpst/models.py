from django.utils.translation import gettext as _
from django.db import models
from functools import reduce
import json
from django.conf import settings
from collections import defaultdict
import copy
import logging

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

    def __hash__(self):
        return hash(self._identifier)

    def __contains__(self, other):
        return self.__eq__(other)

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
            elif isinstance(curr, MsgExc):
                pass
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

        for curr in args[:-1]:
            if not isinstance(curr, MsgExc):
                raise Exception(f"All but the last argument of a Concat should be MsgExc")

        if not isinstance(args[-1], StateVar):
            raise Exception("The last argument of a Concat should be a StateVar")

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

    @property
    def state_vars(self):
        return set()


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

    def simplify(self):
        # credits : Fig. 21, Appendix B.2, "Multiparty Session Types Meet Communicating Automata", Danielou and Yoshida
    
        #breakpoint()


        g1 = GlobalType(self._initial, debug=self.debug)

        for t in self._transforms:   
            g1.add_transform(t)
 
       
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


    def check_wellformed(self):

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
