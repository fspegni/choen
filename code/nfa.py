from rei import REI, Start, End, Symbol, Star, Conc, Par, Union
import random
import string
import itertools
from deprecation import deprecated

EPSILON = ""

class State:

    def __init__(self, id:str = None):
        # use name-mangling (aka double-underscore prefix) 
        # to avoid overwriting the original attribute, thus enforcing 
        # immutability of the object
        if not id:
            id = random_string(8)

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
        # self._pos = pos
        self._positions = []

        if pos > self._input_len:
            raise Exception(f"Position not allowed: {pos}. Input length: {self._input_len}")

        self._positions.append(pos)

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

    # def set_pos(self, pos : int):
    #     self._pos = pos

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

        # self._pos = pos_end
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
        self._initial:State = None
        self._final = set([])

    def __str__(self):
        return f"{len(self.states)} states, {len(self.transitions)} transitions, initial: {self._initial}, {len(self.final)} final states"

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

        #return filter(lambda : curr.source == source, self.transitions.items())
        res = []
        for symbol, transitions in self._transitions.get(source, {}).items():
            if (label is None or symbol == label):
                for t in transitions:
                    assert isinstance(t, Transition)
                    # res.extend(transitions)
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

        return res # [ self._states[id] for id in self._final ]

    """
    Return whether or not the passed state id corresponds to a final state
    """
    def is_final(self, id_state:str) -> bool: 
        if id_state not in self._states:
            raise Exception(f"State {id_state} does not exist")

        return id_state in self._final

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

        

    """
    Return a tuple:
    - bool  : whether the string was recognized
    - State : the final state reached consuming all possible characters from the input string
    - str   : remaining part of input that was not consumed
    """
    def read_string(self, input_string : str, curr_state : str = None):

        iscan = InputScanner(input_string)

        if not self._initial:
            raise Exception(f"Cannot read string without an initial state")
        elif self._initial not in self._states:
            raise Exception(f"Initial state {self._initial} is not a valid state")

        if not curr_state:
            # print(f"Start from initial state: {self._initial}")
            curr_state = self._initial
        
        # pos = 0

        # while pos < len(input_string):
        
        while not iscan.eof:

            # symbol : str = input_string[pos]
            # pos_last = iscan.pos
            # assert pos_last >= 0
            symbol : str = iscan.scan_input()
            #pos = iscan.pos

            # print(f"Read symbol: {symbol} ...")
            # pos = pos  + 1

            if curr_state not in self._transitions:
                # raise Exception(f"State {curr_state} does not have outgoing transitions")
                iscan.undo_reading()
                return False, curr_state, iscan.remaining
            
            # transitions : Transition = self._transitions[curr_state].get(symbol, [])
            transitions = self.transitions_from(curr_state, symbol)
            # print(f"Outgoing transition from {curr_state} with {symbol}: {transitions}")
            e_closure = self.e_closure(curr_state)

            # add to the transition set also the transitions departing from the states in the
            # epsilon-closure starting from current state
            for curr in e_closure:
                if curr.id != curr_state:
                    transitions = transitions.union(self.transitions_from(curr, symbol))

            if len(transitions) == 0:
                # symbol not recognized -> mark as non recognizing, return input not consumed
                iscan.undo_reading()
                return False, self.e_extension(curr_state), iscan.remaining  #input_string[pos-1:]

            elif len(transitions) == 1:
                # deterministic transition -> continue
                curr_state = list(transitions)[0].target.id
            
            else:
                # non deterministic transition -> explore the tree, looking for one recognizing path

                # remaining_shortest = input_string[pos:]
                remaining_shortest = iscan.remaining
                state_shortest = curr_state
                for t_out in transitions:
                    assert isinstance(t_out, Transition)

                    # print(f"Recursive call: read_string({input_string[pos:]},{t_out.target.id}) ...")
                    recognized, reached, remaining = self.read_string(iscan.remaining, t_out.target.id) #self.read_string(input_string[pos:], t_out.target.id)
                    if recognized:
                        return recognized, reached, remaining

                    # store the shortest remaining string, to be returned in case no path can recognize
                    if not remaining_shortest or len(remaining) < len(remaining_shortest):
                        remaining_shortest = remaining
                        state_shortest = reached

                return False, state_shortest, remaining_shortest


        # all input was consumed -> check whether it's in a final state
        # is_final = self.is_final(curr_state)
        # if not is_final:
        #     reachable = list(map(lambda s: s.id, self.e_closure(curr_state)))
        #     # is_final = self.is_final(curr_state)
        #     reachable_final = self._final.intersection(reachable)
        #     if len(reachable_final) > 0:
        #         is_final = True
        #         curr_state = list(reachable_final)[0]
        #     elif len(reachable) > 0:
        #         is_final = False
        #         curr_state = list(reachable)[0]
        curr_state = self.e_extension(curr_state)
        is_final = self.is_final(curr_state)
        remaining = iscan.remaining

        return is_final and len(remaining) == 0, curr_state, remaining # input_string[pos:]


    def e_closure(self, state):

        if isinstance(state, State):
            state = state.id

        assert isinstance(state, str)

        res = set([ self.state(state) ])
        e_transitions = []
        # e_transitions = filter(lambda t: t.label is None or t.label == "", self.transitions_from(state))
        for t in self.transitions_from(state):
            # print(f"Check transition: {t} ...")
            if t.label is None or t.label == "":
                e_transitions.append(t)


        text_transitions = ', '.join(map(lambda t: str(t), e_transitions))
        # print(f"Epsilon transitions from {state}: {text_transitions}")

        for curr in e_transitions:
            # print(f"Check {curr} ...")
            assert isinstance(curr, Transition)

            # print(f"Compare: {curr.target} vs {res}")
            if curr.target != state and curr.target not in res:
                res.add(curr.target)
                ec = self.e_closure(curr.target.id)
                # print(f"Add e-closure: {ec}")
                res = res.union(ec)

        return res

    def e_extension(self, state : str):

        if self.is_final(state):
            return state

        reachable = list(map(lambda s: s.id, self.e_closure(state)))

        reachable_final = list(self._final.intersection(set(reachable)))

        if len(reachable_final) > 0:
            return reachable_final[0]
        elif len(reachable) > 0:
            return reachable[0]
        else:
            return state



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

def random_string(length:int = 8):
    # choose from all lowercase letter
    letters = string.ascii_lowercase
    result_str = ''.join(random.choice(letters) for i in range(length))
    # print("Random string of length", length, "is:", result_str)

    return result_str
