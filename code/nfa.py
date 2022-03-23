from rei import Symbol, Star, Conc, Par, Union

class State:

    def __init__(self, id:str):
        self.id = id


class Transition:

    def __init__(self, source:State, target:State, label:str=None):
        self.source = source
        self.target = target
        self.label = label


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

    def transitions_from(self, source):
        if isinstance(source, State):
            source = source.id

        assert isinstance(source, str)

        return self.transitions.filter(lambda curr: curr.source == source)

    def transitions_to(self, target):
        if isinstance(target, State):
            target = target.id

        assert isinstance(target, str)

        return self.transitions.filter(lambda curr: curr.target == target)

    def transitions_labeled(self, label:str):
        return self.transitions.filter(lambda curr: curr.label == label)

    def add_transition(self, source, target, label):

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

    @property
    def initial(self) -> State:

        if not self._initial:
            return None
        elif self._initial not in self._states:
            raise Exception(f"Wrong configuration: initial state '{self._initial}' does not exist")

        return self._states.get[self._initial]

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

        if not self._initial:
            raise Exception(f"Cannot read string without an initial state")
        elif self._initial not in self._states:
            raise Exception(f"Initial state {self._initial} is not a valid state")

        if not curr_state:
            print(f"Start from initial state: {self._initial}")
            curr_state = self._initial
        
        pos = 0

        while pos < len(input_string):
            symbol : str = input_string[pos]
            print(f"Read symbol: {symbol} ...")
            pos = pos  + 1

            if curr_state not in self._transitions:
                raise Exception(f"State {curr_state} does not have outgoing transitions")
            
                
            transitions : Transition = self._transitions[curr_state].get(symbol, [])
            print(f"Outgoing transition from {curr_state} with {symbol}: {transitions}")

            if len(transitions) == 0:
                # symbol not recognized -> mark as non recognizing, return input not consumed
                return False, curr_state, input_string[pos-1:]

            elif len(transitions) == 1:
                # deterministic transition -> continue
                curr_state = list(transitions)[0].target.id
            
            else:
                # non deterministic transition -> explore the tree, looking for one recognizing path

                remaining_shortest = input_string[pos:]
                state_shortest = curr_state
                for t_out in transitions:
                    assert isinstance(t_out, Transition)

                    print(f"Recursive call: read_string({input_string[pos:]},{t_out.target.id}) ...")
                    recognized, reached, remaining = self.read_string(input_string[pos:], t_out.target.id)
                    if recognized:
                        return recognized, reached, remaining

                    # store the shortest remaining string, to be returned in case no path can recognize
                    if not remaining_shortest or len(remaining) < len(remaining_shortest):
                        remaining_shortest = remaining
                        state_shortest = reached

                return False, state_shortest, remaining_shortest


        # all input was consumed -> check whether it's in a final state
        is_final = self.is_final(curr_state)

        return is_final, curr_state, input_string[pos:]
        


def ReiToNFA(rei):

    if isinstance(rei, Symbol):
        initial = str(rei)

    elif isinstance(rei, Star):
        pass
    elif isinstance(rei, Conc):
        pass
    elif isinstance(rei, Par):
        pass
    elif isinstance(rei, Union):
        pass