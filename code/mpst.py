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

    def to_json(self):

        return str(self._identifier)


class Composition:

    def __init__(self, op : str, *arguments):
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

    def to_json(self):
        return { "type": self.__class__.__name__, "op": self._op, "arguments": list(map(lambda c: c.to_json(), self._arguments)) }


class Fork(Composition):

    def __init__(self, *arguments):
        super().__init__("|{", *arguments)


class Join(Composition):

    def __init__(self, *arguments):
        super().__init__("}|", *arguments)


class Choice(Composition):

    def __init__(self, *arguments):
        super().__init__("+{", *arguments)


class Merge(Composition):

    def __init__(self, *arguments):
        super().__init__("}+", *arguments)


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


    def to_json(self):

        return { "type": self.__class__.__name__, "lhs": self._lhs.to_json(), "rhs": self._rhs.to_json() }



class GlobalType:

    def __init__(self, initial : StateVar, transforms : list = []):
        self._initial = initial

        if transforms:
            for curr in transforms:
                if not isinstance(curr, Transform):
                    raise Exception(f"Expected list of transformations. Received: {transforms}")
            
        self._transforms = transforms
    
    @property
    def participants(self):
        return set(map(lambda c: c.participants, self._transforms))

    @property
    def transforms(self):
        return self._transforms

    def add_transform(self, t : Transform):
        self._transforms.append(t)


    def __str__(self):

        return "def { " + "; ".join(map(lambda c: f"[{c}]", self._transforms)) +  " }  in {self._initial}" 

    def to_json(self):
        
        return { "type": self.__class__.__name__, "initial": self._initial.to_json(), "transforms": list(map(lambda c: c.to_json(), self._transforms))  } 
