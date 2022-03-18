
class State:

    def __init__(self, id:str=default):
        self.id = id

class Transition:

    def __init__(self, source:State, target:State, label:str=null):
        self.source = source
        self.target = target
        self.label

class NFA:

    def __init__(self):
        self._states = {}
        self._transitions = []
        self._initial:State = None
        self._finals = None

    @property
    def initial(self) -> State:
        return self._initial

    @property
    def states(self):
        return self._states.values()

    def state(self, id:str) -> State:
        return self._states.get(id, None)

    @property
    def transitions(self):
        return self._transitions

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

    @property
    def finals(self):
        return self._finals

    @property
    def initial(self):
        return self._initial





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