from rei import Symbol, Star, Conc, Par, Union
import random
import string

EPSILON = ""

class State:

    def __init__(self, id:str):
        self.id = id

    def __str__(self):
        return f"State({self.id})"


class Transition:

    def __init__(self, source:State, target:State, label:str=None):
        self.source = source
        self.target = target
        self.label = label

    def __str__(self):
        return f"{self.source} -[{self.label}]-> {self.target}"

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

    def state(self, id:str) -> State:
        if id not in self._states:
            raise Exception(f"State {id} does not exist")

        return self._states[id]

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

    def transitions_from(self, source, label=None):
        if isinstance(source, State):
            source = source.id

        assert isinstance(source, str)

        #return filter(lambda : curr.source == source, self.transitions.items())
        res = []
        for symbol, transitions in self._transitions.get(source, {}).items():
            if label is None or symbol == label:
                res.extend(transitions)
            
        return res

    def transitions_to(self, target, label=None):
        if isinstance(target, State):
            target = target.id

        assert isinstance(target, str)

        res = []
        for source, dict_transitions in self._transitions.items():
            for symbol, transitions in dict_transitions.items():
                if label is None or label == symbol:
                    for curr in transitions:
                        assert isinstance(curr, Transition)
                        if curr.target.id == target:
                            res.append(curr)

        return res

    def transitions_labeled(self, label:str):
        return filter(lambda curr: curr.label == label, self.transitions)

    def add_transition(self, source, target, label=EPSILON):

        if isinstance(source, State):
            source = source.id

        if isinstance(target, State):
            target = target.id

        source_state = self._states[source]
        target_state = self._states[target]
        transition_set = self._transitions.get(source, {})
        labeled_transition_set = transition_set.get(label, set([]))
        labeled_transition_set.add(Transition(source_state, target_state, label))

        transition_set[label] = labeled_transition_set
        self._transitions[source] = transition_set

    @property
    def final(self):
        res = []

        for curr in self._final:
            if curr not in self._states:
                raise Exception(f"Wrong configuration: final state '{curr}' does not exist")

            res.append(self._states[curr])

        return res # [ self._states[id] for id in self._final ]

    def is_final(self, id_state:str) -> bool: 
        if id_state not in self._states:
            raise Exception(f"State {id_state} does not exist")

        return id_state in self._final

    def set_final(self, state):
        if isinstance(state, State):
            state = state.id

        assert isinstance(state, str)

        if state not in self._states:
            raise Exception(f"State {state} does not exist. Cannot set it final")

        self._final.add(state)

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
                transitions.extend(self.transitions_from(curr, symbol))

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

        return is_final, curr_state, iscan.remaining # input_string[pos:]


    def e_closure(self, state : str):

        res = set([])
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

            print(f"Compare: {curr.target} vs {res}")
            if curr.target != state and curr.target not in res:
                res.add(curr.target)
                ec = self.e_closure(curr.target)
                print(f"Add e-closure: {ec}")
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



def ReiToNFA(rei):

    if isinstance(rei, Symbol):

        id_i = random_string()
        i = State(id_i)

        id_f = random_string()
        f = State(id_f)

        a = NFA()
        a.add_state(i)
        a.add_state(f, is_final=True)

        a.set_initial(i)

        a.add_transition(i, f, rei.symbol)

        return a

    elif isinstance(rei, Star):
        
        a = ReiToNFA(rei.rei)

        for f in rei.rei.final:
            a.add_transition(f, a.initial)

        return a

    elif isinstance(rei, Conc):
        
        a = NFA()

        # first = True
        prev = None

        for curr in rei.items:

            b = ReiToNFA(curr)
            if prev is None: #first:
                a.set_initial(b.initial)
                # first = False

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
        for f in prev.final:
            a.set_final(f)

        return a

    elif isinstance(rei, Par):
        raise Exception("TODO: not implemented yet")

    elif isinstance(rei, Union):
        
        i = State(random_string(8))
        f = State(random_string(8))
        
        a = NFA()
        a.add_state(i)
        a.add_state(f, is_final=True)

        a.set_initial(i)

        for curr in rei.items:
            b = ReiToNFA(curr)

            for s in b.states:
                a.add_state(s)

            for t in b.transitions:
                assert isinstance(t, Transition)
                a.add_transition(t.source, t.target, t.label)

            a.add_transition(i, b.initial)
            for s in b.final:
                a.add_transition(s, f)

        return a              

def random_string(length:int = 8):
    # choose from all lowercase letter
    letters = string.ascii_lowercase
    result_str = ''.join(random.choice(letters) for i in range(length))
    print("Random string of length", length, "is:", result_str)

    return result_str
