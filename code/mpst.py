from functools import reduce

class StateVar:

    def __init__(self, identifier : str):
        self._identifier = identifier

    @property
    def identifier(self):
        return self._identifier

    def __str__(self):
        return self._identifier

    @property
    def participants(self):
        return set([])


class Composition:

    def __init__(self, op : str, arguments):
        self._op = op
        self._arguments = arguments

    def __str__(self):
        num_arguments = len(self._arguments)

        if num_arguments == 1:
            return f"{self._op} {self._arguments[0]}"
        elif num_arguments == 2:
            return f"{self._arguments[0]} {self._op} {self._arguments[1]}"
        else:
            return f"{self._op}({','.join(map(str, self._arguments))})"

    @property
    def participants(self):
        #breakpoint()
        return set(reduce(lambda a,b: a.participants.union(b.participants), self._arguments))


class Fork(Composition):

    def __init__(self, arguments):
        super().__init__("*", arguments)


class Join(Composition):

    def __init__(self, arguments):
        super().__init__("%", arguments)


class Choice(Composition):

    def __init__(self, arguments):
        super().__init__("+", arguments)


class Merge(Composition):

    def __init__(self, arguments):
        super().__init__("-", arguments)


class MsgExc:

    def __init__(self, sender: str, receiver: str, label: str, payload): #, continuation : StateVar):

        if sender == receiver:
            raise Exception("Sender and receiver cannot be the same. Passed: {sender}")

        self._sender = sender
        self._receiver = receiver
        self._label = label
        self._payload = payload
        #self._continuation = continuation

    def __str__(self):
        return f"{self._sender} -> {self._receiver} : {self._label} <{self._payload}>"

    @property
    def participants(self):
        return set([self._sender, self._receiver])


class Concat(Composition):

    def __init__(self, lhs : MsgExc, rhs):
        super().__init__(";", [ lhs, rhs ])


class Transform:

    def __init__(self, lhs : Composition | StateVar, rhs : Composition | StateVar):

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


class GlobalType:

    def __init__(self, initial : StateVar, transforms):
        self._initial = initial
        self._transforms = transforms
    
    @property
    def participants(self):
        return set(map(lambda c: c.participants, self._transforms))

