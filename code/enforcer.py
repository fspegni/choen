import nfa

class Enforcer:

    def __init__(self, nfa : nfa.NFA):
        assert nfa is not None, f"Expected not-null nfa to build an enforcer"
        self._nfa = nfa
        self._buffer = {}
        self._curr_states = set([ self._nfa.initial.id ])

    @property
    def buffer(self) -> dict:
        return self._buffer

    @property
    def curr_states(self) -> str:
        return self._curr_states

    @property
    def nfa(self):
        return self._nfa

    # UTILS

    def buffer_add(self, actor : str, message : str):
        # actor, message = str.split("?")

        actor_buffer = self._buffer.get(actor, {})
        message_counter = actor_buffer.get(message, 0)
        actor_buffer[message] = message_counter + 1
        self._buffer[actor] = actor_buffer

    def buffer_remove(self, actor : str, message : str):

        actor_buffer = self._buffer.get(actor, {})
        message_counter = actor_buffer.get(message, 0)
        assert message_counter >= 0

        if message_counter <= 0:
            raise Exception(f"No message {message} to remove for actor {actor}")
        
        actor_buffer[message] = message_counter - 1
        self._buffer[actor] = actor_buffer

    def buffer_dump(self):
        print("BUFFER:")
        for actor, actor_buffer in self._buffer.items():
            for msg, counter in actor_buffer.items():
                for i in range(counter):
                    print(f"{actor}?{msg}")

    def buffer_has_message(self, actor=None, message=None):
        if actor is not None:
            if actor not in self._buffer:
                return False
            else:
                return message is None or \
                    (message in self._buffer[actor] and self._buffer[actor][message] > 0)

        elif message is not None:
            
            for actor, actor_buffer in self._buffer.items():
                if message in actor_buffer:
                    return True
            
            return False

        else:
            raise Exception("Please, specify either an actor or a message as argument, or both")
        
    def buffer_empty(self) -> bool:
        for actor, actor_buffer in self._buffer.items():
            for msg, counter in actor_buffer.items():
                if counter > 0:
                    return False

        return True

    
    def buffer_find_usable_message(self):
        found = None

        e_closure = self._nfa.e_closure(self._curr_states)

        for actor, actor_buffer in self._buffer.items():
            for message, counter in actor_buffer.items():
                if counter > 0:
                    event = f"{actor}?{message}"
                    for s in e_closure:
                        if self._nfa.transitions_from(s, event):
                            found = (actor, message)
                            break
        
        return found
    
    # PROCESSORS

    def process_input(self, event : str):

        out = None

        if "!" in event:
            # actor, message = event.split("!")
            return self.rule_send(event)

        elif "?" in event:
            actor, message = event.split("?")

            if self.condition_rule_receive_now(event):
                out = self.rule_receive_now(event)
            else:
                # TODO add check that the message may actually be consumed afterwards;
                # without this check, it does not make sense to implement the rule "Cannot receive" 
                out = self.rule_receive_delayed(actor, message)
        
        return out

    def process_check(self):

        out = ""

        try:
            actor, message = self.buffer_find_usable_message()
            out = self.rule_receive_buffered(actor, message)
        except Exception:
            pass

        return out

    # CONDITIONS below

    def condition_rule_receive_now(self, event):

        e_closure = self._nfa.e_closure(self._curr_states)

        for curr in e_closure:
            enabled_transitions = self._nfa.transitions_from(curr, event)

            if len(enabled_transitions) > 0:
                return True

        return False

    # RULES below

    def rule_send(self, event):
        return event

    def rule_receive_now(self, event):
        # accepted, new_state, remaining = self._nfa.read_string(event, self._curr_state)
        # accepted, new_state, remaining = self._nfa.read_symbol(event, self._curr_state)

        reached = set()
        for s in self._curr_states:

            s_reached = self._nfa.read_symbol(event, s)

            assert len(s_reached) > 0, f"Expected to reach some state after consuming event {event}"
            
            reached = reached.union(s_reached)

            # self._curr_states = reached

        self._curr_states = reached
        return event

    def rule_receive_delayed(self, actor, message):
        self.buffer_add(actor, message)
        return ""

    def rule_receive_buffered(self, actor, message):
        
        assert actor in self._buffer and message in self._buffer[actor]
        
        counter = self._buffer[actor][message]

        assert counter > 0

        event = f"{actor}?{message}"

        reached = set()
        # accepted, new_state, remaining = self._nfa.read_string(event, self._curr_state)
        for s in self._curr_states:
            s_reached  = self._nfa.read_symbol(event, s)

            assert len(s_reached) > 0, f"Expected some state is reached after consuming event {event}"

            reached = reached.union(s_reached)
            # self._curr_state = new_state
        
        self.buffer_remove(actor, message)
        # self._buffer[actor][message] = counter - 1   
        self._curr_states = reached

        return event