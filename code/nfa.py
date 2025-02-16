from rei import REI, Start, End, Symbol, Star, Conc, Par, Union
import random
import string
import itertools
from deprecation import deprecated
from graphviz import Digraph

EPSILON = ""

def random_string(length:int = 8):
    # choose from all lowercase letter
    letters = string.ascii_lowercase
    result_str = ''.join(random.choice(letters) for i in range(length))

    return result_str


class State:
 
    counter = 0   

    def __init__(self, id:str = None):
        # use name-mangling (aka double-underscore prefix) 
        # to avoid overwriting the original attribute, thus enforcing 
        # immutability of the object
        if not id:
            #id = random_string(8)
            id = f"state_{State.counter}"
            State.counter = State.counter + 1

        self.__id = id

    def __str__(self):
        return f"State({self.__id})"

    def __hash__(self):
        return hash(hash(str(self)))

    @property
    def id(self):
        return self.__id

    def __eq__(self, other):
        return self.__class__ == other.__class__ and hash(self) == hash(other)

class Transition:

    def __init__(self, source:State, target:State, label:str=None):
        # as State, use name-mangling to enforce immutability of object
        self.__source = source
        self.__target = target
        self.__label = label

    def __str__(self):
        return f"{self.__source} -[{self.__label}]-> {self.__target}"

    def __hash__(self):
        return hash(hash(str(self)))

    def __eq__(self, other):
        return self.__class__ == other.__class__ and hash(self) == hash(other)

    @property
    def source(self):
        return self.__source

    @property
    def target(self):
        return self.__target

    @property
    def label(self):
        return self.__label

class InputScanner:

    def __init__(self, text : str, pos : int = 0):
        self._text = text
        self._input_len = len(text)
        self._positions = []

        if pos > self._input_len:
            raise Exception(f"Position not allowed: {pos}. Input length: {self._input_len}")

        self._positions.append(pos)
        self._frozen = []


    def __enter__(self):

        return self.freeze()
        

    def __exit__(self, *args, **kwargs):
        self.unfreeze()

    def freeze(self):
        curr_len = len(self._positions)
        self._frozen.append(curr_len)
        return curr_len

    def unfreeze(self):
        if len(self._frozen) == 0:
            raise Exception("Too many unfrozen actions happend on this scanner")

        curr_len = self._frozen.pop()
        del self._positions[curr_len:]

    @property
    def eof(self) -> bool:
        return self.pos >= self._input_len

    @property
    def bof(self) -> bool:
        return self.pos == 0

    @property
    def pos(self) -> int:
        if len(self._positions) == 0:
            raise Exception("Unexpected empty stack of positions")

        return self._positions[-1]

    @property
    def remaining(self):
        return self._text[self.pos:]

    def scan_input(self) -> str:
        if self.eof:
            raise Exception("End-of-file reached")

        if self.pos < 0:
            raise Exception(f"Position not allowed in string. Position: {self._pos}. Input length: {self._input_len}")

        pos_start = self.pos
        delimiter = " "

        if self._text[pos_start] in [ " ", "'" ]:
            delimiter = self._text[pos_start]
            pos_start = pos_start + 1
            
        pos_end = pos_start
        token = ""
        while pos_end < self._input_len and self._text[pos_end] != delimiter:
            token = token + self._text[pos_end]
            pos_end = pos_end + 1

        if delimiter != " " and self._text[pos_end] != delimiter:
            raise Exception(f"End reached without finding expected delimiter ({delimiter})")

        token = self._text[pos_start:pos_end]
        pos_end = pos_end + 1

        # consume final spaces if present
        while pos_end < self._input_len and self._text[pos_end] == " ":
            pos_end = pos_end + 1

        self._positions.append(pos_end)

        return token

    def undo_reading(self) -> int:
        if len(self._positions) == 0:
            raise Exception("Cannot undo reading anymore. Reading stack empty")
        if len(self._positions) == 1:
            raise Exception(f"Cannot undo reading anymore. Reached the initial position: {self._positions[0]}")

        pos_prev = self._positions.pop()
        return pos_prev
    

class NFA:

    def __init__(self):
        self._states = {}
        self._transitions = {}
        self._initial:str = None
        self._final = set([])
        self._iscan : InputScanner = None
        self._event_dictionary = {}
        self._event_dictionary_lookup = {}

    def __str__(self):
        return f"{len(self.states)} states, {len(self.transitions)} transitions, initial: {self._initial}, {len(self.final)} final states"


    def to_dot(self):
        g = Digraph(name='curr_graph', filename='curr_graph.gv')
        g.graph_attr["rankdir"] = "LR"
        #g.graph_attr["beautify"] = "true"
        g.attr("node", shape="point") #, width="0.1")
        for k,s in self._states.items():
#            print(f"Add node: {s.id} ...")
            g.node(s.id, label="")

        g.attr("edge", arrowsize="0.5")
        for source,tr_dict in self._transitions.items():
            for label, tr_set in tr_dict.items():
                label = self._event_dictionary[label] if label else "<&#949;>"
                for tr in tr_set:
#                    print(f"Add transition: {tr.source} -> {tr.target} ...")
                    #label = tr.label if tr.label else "<&#949;>"
                    g.edge(tr.source.id, tr.target.id, label=label)

#        g.render(format="png")
#        print(g)
        return g
     
    @property
    def event_dictionary(self):
        return self._event_dictionary_lookup
   

    @property
    def iscan(self) -> InputScanner:
        return self._iscan

    @property
    def states(self):
        return self._states.values()

    def get_state(self, id:str) -> State:
        if id not in self._states:
            raise Exception(f"State {id} does not exist")

        return self._states[id]

    @deprecated(details="Use the getter 'get_state'")
    def state(self, id:str) -> State:
        return self.get_state(id)

    def add_state(self, new_state:State, is_final:bool=False):
        self._states[new_state.id] = new_state

        if is_final:
            self._final.add(new_state.id)

    @property
    def transitions(self):
        res = []
        for source, transitions_set in self._transitions.items():
            for symbol, targets in transitions_set.items():
                res.extend(targets)


        return res

    """
    Return the set of all transitions departing from the passed source state. If a label is 
    specified, only those transitions that share that label are returned.
    """
    def transitions_from(self, source, label=None, target=None):
        if isinstance(source, State):
            source = source.id

        assert isinstance(source, str)

        if target and isinstance(target, State):
            target = target.id

        assert target is None or isinstance(target, str)

        res = []
        for symbol, transitions in self._transitions.get(source, {}).items():
            if (label is None or symbol == label):
                for t in transitions:
                    assert isinstance(t, Transition)
                    if target is None or t.target.id == target:
                        res.append(t)
            
        return set(res)

    """
    Return the set of all transitions reaching the passed target state. If a label is specified,
    only thos transitions that share that label are returned.
    """
    def transitions_to(self, target, label=None, source=None):
        if isinstance(target, State):
            target = target.id

        assert isinstance(target, str)

        if source and isinstance(source, State):
            source = source.id

        assert source is None or isinstance(source, str)

        res = []
        for s, dict_transitions in self._transitions.items():
            if source and source != s:
                continue

            for symbol, transitions in dict_transitions.items():
                if label is None or label == symbol:
                    for curr in transitions:
                        assert isinstance(curr, Transition)
                        if curr.target.id == target:
                            res.append(curr)

        return set(res)

    def transitions_labeled(self, label:str):
        return filter(lambda curr: curr.label == label, self.transitions)

    """
    This is just an alias
    """
    def transitions_from_to(self, source, target, label=None):
        return self.transitions_from(source, label=label, target=target)

    """
    Add a transition to the automaton. Note that since transitions are immutable objects,
    we identify transitions that have the same source *and* same target *and* same label. 
    As a consequence, in case two identical transitions are added to the same automaton, only
    one will be returned later on.
    """
    def add_transition(self, source, target, label=EPSILON):

        if isinstance(source, State):
            source_state = source
            source = source.id
        else:
            source_state = self._states[source]
        
        assert isinstance(source, str)
        assert isinstance(source_state, State)

        if isinstance(target, State):
            target_state = target
            target = target.id
        else:
            target_state = self._states[target]
        
        assert isinstance(target, str)
        assert isinstance(target_state, State)

        transition_set = self._transitions.get(source, {})
        labeled_transition_set = transition_set.get(label, set([]))
        labeled_transition_set.add(Transition(source_state, target_state, label))

        transition_set[label] = labeled_transition_set
        self._transitions[source] = transition_set

        if label and label not in self._event_dictionary:
            new_code = self._generate_label_code()
            self._event_dictionary[label] = new_code
            self._event_dictionary_lookup[new_code] = label

    def _generate_label_code(self):
        # TODO note that this works only for limited sets of symbols
        return chr(ord('A') + len(self._event_dictionary.items())) 

    """
    Return the states that are actually final states
    """
    @property
    def final(self):
        res = []

        for curr in self._final:
            if curr not in self._states:
                raise Exception(f"Wrong configuration: final state '{curr}' does not exist")

            res.append(self._states[curr])

        return res 

    """
    Return whether or not the passed states contain at least one final (accepting) state
    """
    def is_final(self, states) -> bool:
        if isinstance(states, State):
            states = set([ states.id ])
        elif isinstance(states, str):
            states = set([ states ])

        assert isinstance(states, ( set, list ))

        for s in states:
            if s not in self._states:
                raise Exception(f"State {s} does not exist")

            if s in self._final:
                return True
        
        return False

    def is_initial(self, state):
        if isinstance(state, State):
            state = state.id
        
        return self._initial == state

    """
    Add one or more states to the set of final states
    """
    def add_final(self, *states):
        
        for state in states:
            if isinstance(state, State):
                state = state.id

            assert isinstance(state, str)

            if state not in self._states:
                raise Exception(f"State {state} does not exist. Cannot set it final")

            self._final.add(state)

    """
    Replace the entire set of final states with the newly passed list of states
    """
    def set_final(self, *states):
        prev_final = self._final.copy()

        self._final.clear()
        try:
            self.add_final(*states)
        except Exception as e:
            # in case of errors, restore previous final states
            self._final = prev_final
            raise e

    @property
    def initial(self) -> State:

        if not self._initial:
            return None
        elif self._initial not in self._states:
            raise Exception(f"Wrong configuration: initial state '{self._initial}' does not exist")

        return self._states[self._initial]



    def set_initial(self, state):
        if isinstance(state, State):
            state = state.id

        assert isinstance(state, str)

        self._initial = state

    """"
    This chould be used in a with ... block
    """
    def scan_input(self, input_string):

        try:
            self._iscan = InputScanner(input_string)
            yield
        finally:
            self._iscan = None


    """
    Return a tuple:
    - bool  : whether the string was recognized
    - State : the final state reached consuming all possible characters from the input string
    - str   : remaining part of input that was not consumed
    """
    def read_string(self, input_string : str, curr_state = None):

        res = None
        try:
            self._iscan = InputScanner(input_string)

            res = self.do_read(curr_state)
        finally:
            self._iscan = None

        return res


    def do_read(self, initial_state = None):

        if not self._initial:
            raise Exception(f"Cannot read string without an initial state")
        elif self._initial not in self._states:
            raise Exception(f"Initial state {self._initial} is not a valid state")

        curr_state = initial_state
        if not curr_state:
            curr_state = self._initial
        elif isinstance(curr_state, State):
            curr_state = curr_state.id

        assert isinstance(curr_state, str), f"Expected string, received: {curr_state}"
        
        reached = set()


        with self._iscan:

            while not self._iscan.eof:

                symbol : str = self._iscan.scan_input()

                reached = self.read_symbol(symbol, curr_state)
                num_reached = len(reached)

                if num_reached == 0:
                    self._iscan.undo_reading()
                    new_state, _ = self.e_extension(curr_state)
                    return False, set([new_state]), self._iscan.remaining    
                elif num_reached == 1:
                    # deterministic transition -> continue
                    curr_state = reached.pop()
                else:
                    # non deterministic transition -> explore the tree, looking for one recognizing path
                    remaining_shortest = None
                    remaining_reachable = set()
                    accepting_reachable = set()

                    for s in reached:
                        assert isinstance(s, str)

                        accepted, s_next, remaining = self.do_read(s) 


                        if accepted:
                            assert remaining == ""
                            accepting_reachable = accepting_reachable.union(s_next)
                        else:
                            if remaining_shortest is None or len(remaining) < len(remaining_shortest):
                                remaining_shortest = remaining
                                remaining_reachable = s_next
                            elif remaining_shortest == remaining:
                                remaining_reachable = remaining_reachable.union(s_next)

                    if accepting_reachable:
                        return True, accepting_reachable, ""
                    else:
                        return False, remaining_reachable, remaining_shortest

            e_closure = self.e_closure(curr_state)
            remaining = self._iscan.remaining
            is_accepted = self.is_final(e_closure)

            return is_accepted, e_closure, remaining 



    def read_symbol(self, symbol : str, curr_state : str):

            reached = set([])

            if curr_state not in self._transitions:
                return set()
            
            transitions = self.transitions_from(curr_state, symbol)
            e_closure = self.e_closure(curr_state)

            # add to the transition set also the transitions departing from the states in the
            # epsilon-closure starting from current state
            for curr in e_closure:
                if curr != curr_state:
                    transitions = transitions.union(self.transitions_from(curr, symbol))

            if len(transitions) == 0:
                return set()

            elif len(transitions) == 1:
                # deterministic transition -> continue
                curr_state = list(transitions)[0].target
                reached.add(curr_state.id)

            else:
                # non deterministic transition -> explore the tree, looking for one recognizing path

                for t_out in transitions:
                    assert isinstance(t_out, Transition)

                    reached.add(t_out.target.id)

            for curr in reached:
                reached = reached.union(self.e_closure(curr))

            return reached

    """
    Returns a set of state reachable starting at the passed state by using only epsilon transitions
    """
    def e_closure(self, states) -> set:

        if isinstance(states, State):
            states = set([ states.id ])
        elif isinstance(states, str):
            states = set([ states ])
            
        assert isinstance(states, set), f"A single state or a set of states was expected. Received: {states}"

        res = states


        e_transitions = []
        for s in states:
            for t in self.transitions_from(s):
                if t.label is None or t.label == "":
                    e_transitions.append(t)


        for curr in e_transitions:
            assert isinstance(curr, Transition)

            if curr.target.id not in res:
                ec = self.e_closure(curr.target.id)
                res = res.union(ec)

        return res

    """
    Tries to reach a final state by consuming as much epsilon-transitions as possible.

    Returns a pair:
    - str  : a state id reached after consuming zero or more empty transitions
    - bool : whether the returned state is final or not
    """
    def e_extension(self, state) -> str:

        if isinstance(state, State):
            state = state.id

        assert isinstance(state, str)

        result = None
        if self.is_final(state):
            result = (state, True)
        else:
            reachable = self.e_closure(state)

            reachable_final = list(self._final.intersection(set(reachable)))

            if len(reachable_final) > 0:
                result = (reachable_final.pop(), True)
            elif len(reachable) > 0:
                result = (reachable.pop(), False)
            else:
                result = (state, False)

        return result


def ReiToNFA(rei : REI) -> NFA:

    if isinstance(rei, Start) or isinstance(rei, End):
        s = State()
        a = NFA()

        a.add_state(s, is_final=True)
        a.set_initial(s)
        return a

    elif isinstance(rei, Symbol):

        i = State()
        f = State()

        a = NFA()
        a.add_state(i)
        a.add_state(f, is_final=True)

        a.set_initial(i)

        a.add_transition(i, f, rei.symbol)

        return a

    elif isinstance(rei, Star):
        
        a : NFA = ReiToNFA(rei.rei)

        for f in a.final:
            a.add_transition(f, a.initial)

        a.add_final(a.initial)

        return a

    elif isinstance(rei, Conc):
        assert len(rei.items) > 0
        
        a = NFA()

        prev = None

        for curr in rei.items:

            b = ReiToNFA(curr)
            if prev is None:
                a.set_initial(b.initial)

            for s in b.states:
                a.add_state(s)

            for t in b.transitions:
                assert isinstance(t, Transition)

                a.add_transition(t.source, t.target, t.label)

            if prev is not None:
                for f in prev.final:
                    a.add_transition(f, b.initial)

            prev = b

        assert prev is not None
        a.set_final(*prev.final)

        return a

    elif isinstance(rei, Par):
        assert len(rei.items) > 0

        a = NFA()

        nfa_children = []
        state_ids = []
        state_ids_initial = []

        # the i-th element is a mapping from the states in the i-th automaton 
        # to the composite (product) states induced by it
        # state_ids_map = []

        for curr in rei.items:
            assert isinstance(curr, REI)

            b = ReiToNFA(curr)
            nfa_children.append(b)

            automata_state_ids = map(lambda s: s.id, b.states)
            state_ids.append(automata_state_ids)
            state_ids_initial.append(b.initial.id)

        for sid_parts in itertools.product(*state_ids):
            sid_composite = "__".join(sid_parts)

            is_final = True
            for nfa,sid in zip(nfa_children, sid_parts):
                assert isinstance(nfa, NFA)
                assert isinstance(sid, str)

                is_final = nfa.is_final(sid)
                if not is_final:
                    break
                
            a.add_state(State(sid_composite), is_final=is_final)

        for s in a.states:
            s_parts = s.id.split("__")
            
            for t in a.states:
                t_parts = t.id.split("__")

                # -1 : not found
                # -2 : too many differences
                # >= 0 : exactly one difference at the stored position
                pos_diff = -1
                for pos, (s_sid, t_sid) in enumerate(zip(s_parts, t_parts)):
                    # TODO the condition below does not allow to capture/translate loops
                    if s_sid != t_sid:
                        if pos_diff >= 0:
                            pos_diff = -2
                            break
                        else:
                            pos_diff = pos

                if pos_diff >= 0:
                    source = s_parts[pos_diff]
                    target = t_parts[pos_diff]
                    transitions = nfa_children[pos_diff].transitions_from_to(source, target)    
                    for tran in transitions:
                        assert isinstance(tran, Transition)
                        a.add_transition(s, t, tran.label)


        a.set_initial("__".join(state_ids_initial))
    
        return a

    elif isinstance(rei, Union):
        assert len(rei.items) > 0
        
        i = State()
        
        a = NFA()
        a.add_state(i)

        a.set_initial(i)

        for curr in rei.items:
            b = ReiToNFA(curr)

            for s in b.states:
                a.add_state(s)

            for t in b.transitions:
                assert isinstance(t, Transition)
                a.add_transition(t.source, t.target, t.label)

            a.add_transition(i, b.initial)
            a.add_final(*b.final)

        return a              
