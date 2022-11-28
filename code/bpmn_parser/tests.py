from audioop import add
from django.test import TestCase
import solcx
import os
from django.conf import settings
from enforcer_generator import EnforcerGenerator
from enforcer_deployer import EnforcerDeployer

from bpmn_parser.models import Choreography, NS, ElementType
from enforcer import Enforcer
from nfa import NFA
import rei
import nfa
import contracts
from contracts import SmartContract
import json
from web3 import Web3
import requests

class TestChoreographyBasicCase(TestCase):

    def setUp(self):

        choreographies = [
            ("diagram", "diagram.bpmn", ),
            ("diagram_gateways", "diagram_gateways.bpmn", ),
        ]

        for name, filename in choreographies:
            c:Choreography = Choreography()
            c.name = name
            c.resource = os.path.join(settings.MEDIA_ROOT, filename)
            c.save()


    def test_compilation(self):

        c:Choreography = Choreography.objects.get(name="diagram")
        text = c.compile()
        assert len(text) > 0
        solc_version = "0.7.6"
        assert solc_version in text
        res = solcx.compile_source(text, solc_version=solc_version)

        key = "<stdin>:" + c.choreographies[0].attrib["id"]
        assert type(res) == dict
        assert key in res
        assert type(res[key]) == dict


    def test_next(self):

        c:Choreography = Choreography.objects.get(name="diagram")

        assert len(c.startEvents) == 1

        curr = c.startEvents[0]
        # for curr in c.startEvents:

        assert len(c.outgoing(curr)) == 1

        # print("START: %s" % curr)
        next = c.next(curr)
        # print("NEXT: %s" % next)

        assert(len(next) == 1)
        assert(next[0].attrib["name"] == "order pizza")

        for curr in c.endEvents:
            next = c.next(curr)
            assert len(next) == 0


    def test_prev(self):

        c:Choreography = Choreography.objects.get(name="diagram")

        assert len(c.endEvents) == 1

        curr = c.endEvents[0]

        assert len(c.incoming(curr)) == 1

        # for curr in c.endEvents:
        # print(">>> END: %s" % curr)
        prev = c.prev(curr)
        # print(">>> PREV: %s" % prev)

        assert len(prev) == 1
        assert prev[0].attrib["name"] == "deliver pizza"

        for curr in c.startEvents:
            prev = c.prev(curr)
            assert len(prev) == 0

    def test_next_star(self):

        c:Choreography = Choreography.objects.get(name="diagram")
        # for curr in c.startEvents:
        curr = c.startEvents[0]

        # print("START: %s" % curr)
        items = c.star(curr, c.next)
        # print("ITEMS = %s" % items)

        # expected to return itself plus 4 reachable items
        assert len(items) == 5, f"Found {len(items)} items"


    def test_prev_star(self):

        c:Choreography = Choreography.objects.get(name="diagram")
        for curr in c.endEvents:
            # print("END: %s" % curr)
            items = c.star(curr, c.prev)
            # print("ITEMS = %s" % items) 


    def test_reachable(self):

        c:Choreography = Choreography.objects.get(name="diagram")
        # for curr in c.startEvents:
        curr = c.startEvents[0]

        # print("START: %s" % curr)
        items = c.reachable(curr)
        # print("ITEMS = %s" % items)

        # expected to return itself plus 4 reachable items
        assert len(items) == 5, f"Found {len(items)} items"


    def test_gateways(self):

        c:Choreography = Choreography.objects.get(name="diagram_gateways")
        # for curr in c.startEvents:
        # curr = c.startEvents[0]

        assert len(c.gw_parallel) == 0
        assert len(c.gw_exclusive) == 2


    def test_visit_neighbor(self):
        """
        This test case shows also how to build a visitor using the next(...) function
        """
        
        c:Choreography = Choreography.objects.get(name="diagram_gateways")
        
        curr = c.startEvents[0]

        to_visit = set([ curr ])
        visited = set([])
        n_visited = 0

        while len(to_visit) > 0:

            curr = to_visit.pop()
            visited.add(curr)

            n_visited = n_visited + 1
            # print(f">> TO VISIT: {curr} ({curr.attrib['id']})")

            arcs = c.outgoing(curr)
            # assert len(arcs) == 1, f"Found {len(arcs)} outgoing arcs from {curr} ({curr.attrib['id']})"
            # print(f">> ARCS: {arcs}")

            if len(arcs) > 0:
                neighbors = c.next(curr, arcs)
                assert len(neighbors) == len(arcs), f"Received: neighbors : {neighbors} : arcs : {arcs}"

                # remove from the neighbors, those that have been visited
                neighbors_unvisited = set(neighbors).difference(visited)
                to_visit = to_visit.union(set(neighbors_unvisited))
            else:
                neighbors = c.next(curr)
                assert len(neighbors) == 0

        n_start = len(c.startEvents)
        n_end = len(c.endEvents)
        n_tasks = len(c.tasks)
        n_gateways = len(c.gateways)

        assert n_visited == n_start + n_end + n_tasks + n_gateways, f"Visited: {n_visited} : Start: {n_start} : End: {n_end} : Tasks: {n_tasks} : Gateways: {n_gateways}"

    def test_start_events_have_no_participants(self):

        c:Choreography = Choreography.objects.get(name="diagram_gateways")

        for curr in c.startEvents:
            participants = c.involved(curr)

            assert len(participants) == 0


    def test_end_events_have_no_participants(self):

        c:Choreography = Choreography.objects.get(name="diagram_gateways")

        for curr in c.endEvents:
            participants = c.involved(curr)

            assert len(participants) == 0

    def test_gateways_have_no_participants(self):

        c:Choreography = Choreography.objects.get(name="diagram_gateways")

        for curr in c.gateways:
            participants = c.involved(curr)

            assert len(participants) == 0


    def test_start_events_have_no_messages(self):

        c:Choreography = Choreography.objects.get(name="diagram_gateways")

        for curr in c.startEvents:
            messages = c.messages(curr)

            assert len(messages) == 0

    def test_end_events_have_no_messages(self):

        c:Choreography = Choreography.objects.get(name="diagram_gateways")

        for curr in c.endEvents:
            messages = c.messages(curr)

            assert len(messages) == 0

    def test_gateways_have_no_messages(self):

        c:Choreography = Choreography.objects.get(name="diagram_gateways")

        for curr in c.gateways:
            messages = c.messages(curr)

            assert len(messages) == 0


    def test_tasks_have_at_least_one_message(self):

        c:Choreography = Choreography.objects.get(name="diagram_gateways")

        for curr in c.tasks:
            messages = c.messages(curr)

            assert len(messages) > 0



"""
TODO test loops/star
"""
class TestChoreographyToRei(TestCase):

    def setUp(self):

        choreographies = [
            ("diagram", "diagram.bpmn", ),
            ("diagram_minimal", "diagram_minimal.bpmn"),
            ("diagram_basic", "diagram_basic.bpmn"),
            ("diagram_gateways", "diagram_gateways.bpmn", ),
            ("diagram_gateways_mismatch", "diagram_gateways_mismatch.bpmn", ),
            ("diagram_gateways_dangling", "diagram_gateways_dangling.bpmn", ),
            ("diagram_gateways_nested", "diagram_gateways_nested.bpmn", ),
            ("diagram_gateways_nested_intermediate", "diagram_gateways_nested_with_intermediate_task.bpmn", ),
            ("diagram_gateways_nested_inclusive", "diagram_gateways_nested_inclusive.bpmn", ),
            ("diagram_gateways_nested_dangling", "diagram_gateways_nested_dangling.bpmn", ),

        ]

        for name, filename in choreographies:
            c:Choreography = Choreography()
            c.name = name
            c.resource = os.path.join(settings.MEDIA_ROOT, filename)
            c.save()
            

    def test_translation_only_start(self):
        """
        This diagram contains only a start event
        """
        c:Choreography = Choreography.objects.get(name="diagram_minimal")

        print(f"{NS}")
        # print(f">>> START: {c.startEvents}")
        print(f"{type(c.startEvents[0])}")

        r, match = rei.ChoToRei(c)

        print(f"REI ({c.name}): {r}")
        print(f"REI ({c.name},latex): {r.latex}")

        assert str(r) == "^$"


    def test_translation_start_end(self):
        """
        This diagram contains only a start event followed by an end event
        """
        c:Choreography = Choreography.objects.get(name="diagram_basic")

        # print(f">>> START: {c.startEvents}")


        r, match = rei.ChoToRei(c)

        print(f"REI ({c.name}): {r}")
        print(f"REI ({c.name},latex): {r.latex}")

        assert str(r) == "^$", f"Received: {r}"

  
    def test_translation_simple(self):

        c:Choreography = Choreography.objects.get(name="diagram")
        
        r, match = rei.ChoToRei(c)

        print(f"REI ({c.name}): {r}")
        print(f"REI ({c.name},latex): {r.latex}")

        assert str(r) == "^'order pizza' 'hand over pizza' 'deliver pizza'$", f"Received: {r}"

    
    def test_translation_gateways(self):

        c:Choreography = Choreography.objects.get(name="diagram_gateways")
        
        r, match = rei.ChoToRei(c)

        print(f"REI ({c.name}): {r}")
        print(f"REI ({c.name},latex): {r.latex}")

        assert str(r) == "^'order pizza' ('New Activity' | 'hand over pizza' 'deliver pizza')$", f"Received: {r}"

    def test_translation_gateways_mismatch(self):

        c:Choreography = Choreography.objects.get(name="diagram_gateways_mismatch")
        

        with self.assertRaises(AssertionError) as context:
            r, match = rei.ChoToRei(c)
        

    def test_translation_gateways_dangling(self):

        c:Choreography = Choreography.objects.get(name="diagram_gateways_dangling")

        r, match = rei.ChoToRei(c)

        print(f"REI ({c.name}): {r}")
        print(f"REI ({c.name},latex): {r.latex}")

        assert str(r) == "^'order pizza' ('New Activity'$ | 'hand over pizza' 'deliver pizza'$)", f"Received: {r}"

        
    def test_translation_gateways_nested(self):

        c:Choreography = Choreography.objects.get(name="diagram_gateways_nested")
        
        r, match = rei.ChoToRei(c)

        print(f"REI ({c.name}): {r}")
        print(f"REI ({c.name},latex): {r.latex}")

        assert str(r) == "^'order pizza' ('New Activity' | 'hand over pizza' 'deliver pizza' (Something 'Something else' & 'Another task'))$", f"Received: {r}"


    def test_translation_gateways_nested_inclusive(self):

        c:Choreography = Choreography.objects.get(name="diagram_gateways_nested_inclusive")
        
        r, match = rei.ChoToRei(c)

        print(f"REI ({c.name}): {r}")
        print(f"REI ({c.name},latex): {r.latex}")

        assert str(r) == "^'order pizza' (('' | 'New Activity') & ('' | 'hand over pizza' 'deliver pizza' (Something 'Something else' & 'Another task')))$", f"Received: {r}"

    
    def test_translation_gateways_nested_intermediate(self):

        c:Choreography = Choreography.objects.get(name="diagram_gateways_nested_intermediate")
        
        r, match = rei.ChoToRei(c)

        print(f"REI ({c.name}): {r}")
        print(f"REI ({c.name},latex): {r.latex}")

        assert str(r) == "^'order pizza' ('New Activity' | 'hand over pizza' 'deliver pizza' (Something 'Something else' & 'Another task') Intermediate)$", f"Received: {r}"


    def test_translation_gateways_nested_dangling(self):

        c:Choreography = Choreography.objects.get(name="diagram_gateways_nested_dangling")

        r, match = rei.ChoToRei(c)


        print(f"REI ({c.name}): {r}")
        print(f"REI ({c.name},latex): {r.latex}")

        # TODO Check tasks without outgoing arrows in BPMN semantics
        # TODO remove intermediate dollars, add just a final dollar
        assert str(r) == "^'order pizza' ('New Activity' ('another implicit end'$ & (('' | 'implicit end'$) & ('' | something 'something else'$))) | 'hand over pizza' 'deliver pizza'$)", f"Received: {r}"

    def test_translation_with_messages(self):

        c:Choreography = Choreography.objects.get(name="diagram_gateways_nested_dangling")

        r, match = rei.ChoToRei(c, rei.render_receive)

        print(f"REI ({c.name}): {r}")
        print(f"REI ({c.name},latex): {r.latex}")

        assert str(r) == "^Pizza_Place?pizza_order (Pizza_Place?Message_0rkgt7n (Customer?Message_10fwh9y$ & (('' | Customer?Message_1e83pou$) & ('' | Customer?Message_0futku6 Pizza_Place?Message_1nqt44e$))) | Delivery_Boy?Message_1mi4idx Customer?pizza$)", f"Received: {r}"


class TestNFA(TestCase):

    def test_state(self):

        s = nfa.State("foo")

        assert s.id == "foo"

    def test_state_identity(self):

        s1 = nfa.State("foo")
        s2 = nfa.State("fie")
        s3 = nfa.State("foo")

        assert s1 is not s2
        assert s2 is not s3
        assert s1 is not s3

        assert s1 != s2
        assert s1 == s3
        assert s2 != s3


        assert len(set([s1,s2,s3,s2,s3])) == 2

    def test_transition(self):
        s1 = nfa.State("foo")
        s2 = nfa.State("fie")
        t = nfa.Transition(s1, s2, "boo")

        assert t.source == s1
        assert t.target == s2
        assert t.label == "boo"

    def test_transition_identity(self):
        s1 = nfa.State("foo")
        s2 = nfa.State("fie")
        s3 = nfa.State("foo")

        t1 = nfa.Transition(s1, s2, "foo")
        t2 = nfa.Transition(s1, s2)
        t3 = nfa.Transition(s1, s2, "fez")
        t4 = nfa.Transition(s1, s2)
        t5 = nfa.Transition(s2, s1, "foo")
        t6 = nfa.Transition(s1, s2, "foo")

        assert t1 is not t6
        assert t1 == t6

        assert t1 != t5
        
        assert t1 != t2
        assert t2 == t4
        assert t1 != t4

        assert t1 == nfa.Transition(s1, s2, "foo")

        assert len(set([t1,t2,t3,t4,t5,t6])) == 4

    def test_empty_automaton(self):
        a = nfa.NFA()

        assert len(a.states) == 0, f"States: {a.states}"
        assert len(a.transitions) == 0, f"Transitions: {a.transitions}"
        assert len(a.final) == 0
        assert a.initial == None

        with self.assertRaises(Exception) as context:
            result, states, remaining = a.read_string("foofie")


    def test_final_states(self):

        s1 = nfa.State("s1")
        s2 = nfa.State("s2")
        s3 = nfa.State("s3")
        s4 = nfa.State("s4")
        s5 = nfa.State("s5")

        a = nfa.NFA()
        a.add_state(s1)
        a.add_state(s2)
        a.add_state(s3, is_final=True)
        a.add_state(s4)
        a.add_state(s5, is_final=True)

        assert len(a.final) == 2

        for curr in a.final:
            assert curr in [ s3, s5 ]

        for curr in [ s3, s5 ]:
            assert curr in a.final

    def test_transition_operators(self):

        s1 = nfa.State("s1")
        s2 = nfa.State("s2")
        s3 = nfa.State("s3")
        s4 = nfa.State("s4")
        s5 = nfa.State("s5")

        a = nfa.NFA()
        a.add_state(s1)
        a.add_state(s2)
        a.add_state(s3)
        a.add_state(s4)
        a.add_state(s5, is_final=True)

        a.add_transition(s1, s2, "a")
        a.add_transition(s2, s3) # epsilon transition
        a.add_transition(s2, s4) # epsilon transition
        a.add_transition(s3, s4, "b")
        a.add_transition(s3, s5, "c")
        a.add_transition(s3, s5) # epsilon transition
        a.add_transition(s5, s1) # epsilon transition
        a.add_transition(s4, s1, "d")

        transitions = list(a.transitions_from(s1))
        assert len(transitions) == 1, f"Received: {transitions}"
        assert transitions[0].source == s1

        transitions = list(a.transitions_from(s2))
        transitions_text = ", ".join(map(lambda t: str(t), transitions))
        assert len(transitions) == 2, f"Received: {transitions}"
        for t in transitions:
            assert t.source == s2

        transitions = list(a.transitions_from(s3))
        assert len(transitions) == 3, f"Received: {transitions}"
        for t in transitions:
            assert t.source == s3

        transitions = list(a.transitions_from(s4))
        assert len(transitions) == 1, f"Received: {transitions}"
        assert transitions[0].source == s4

        transitions = list(a.transitions_from(s5))
        assert len(transitions) == 1, f"Received: {transitions}"
        assert transitions[0].source == s5

        transitions = list(a.transitions_to(s3))
        assert len(transitions) == 1
        assert transitions[0].target == s3

        transitions = list(a.transitions_to(s5))
        assert len(transitions) == 2
        for t in transitions:
            assert t.target == s5


    def test_epsilon_closure(self):
        s1 = nfa.State("s1")
        s2 = nfa.State("s2")
        s3 = nfa.State("s3")
        s4 = nfa.State("s4")
        s5 = nfa.State("s5")

        a = nfa.NFA()
        a.add_state(s1)
        a.add_state(s2)
        a.add_state(s3)
        a.add_state(s4)
        a.add_state(s5, is_final=True)

        a.add_transition(s1, s2, "a")
        a.add_transition(s2, s3) # epsilon transition
        a.add_transition(s2, s4) # epsilon transition
        a.add_transition(s3, s4, "b")
        a.add_transition(s3, s5, "c")
        a.add_transition(s3, s5) # epsilon transition
        a.add_transition(s5, s1) # epsilon transition
        a.add_transition(s4, s1, "d")

        a.set_initial(s1)

        c = a.e_closure(s1)
        assert len(c) == 1, f"Received: {c}"
        assert c == set([s1.id])

        c = a.e_closure(s2)
        assert len(c) == 5, f"Received: {c}"
        assert c == set([ s1.id, s2.id, s3.id, s4.id, s5.id ])

        c = a.e_closure(s4)
        assert len(c) == 1, f"Received: {c}"
        assert c == set([ s4.id ])

        c = a.e_closure(s5)
        assert len(c) == 2, f"Received: {c}"
        assert c == set([ s1.id, s5.id ])

    def test_automaton_linear(self):
        s1 = nfa.State("s1")
        s2 = nfa.State("s2")
        s3 = nfa.State("s3")
        s4 = nfa.State("s4")
        s5 = nfa.State("s5")

        a = nfa.NFA()
        a.add_state(s1)
        a.add_state(s2)
        a.add_state(s3)
        a.add_state(s4)
        a.add_state(s5, is_final=True)

        a.add_transition(s1, s2, "a")
        a.add_transition(s2, s3, "b")
        a.add_transition(s3, s4, "c")
        a.add_transition(s4, s5, "d")

        a.set_initial(s1)

        accepted, states, remaining = a.read_string("a b c d")
        assert accepted == True
        assert s5.id in states
        assert remaining == ""

    def test_automaton_loop(self):

        s1 = nfa.State("s1")
        s2 = nfa.State("s2")
        
        a = nfa.NFA()
        a.add_state(s1)
        a.add_state(s2, is_final=True)

        a.set_initial(s1)

        # automaton recognizing (a b*) (a a b*)*
        a.add_transition(s1, s2, "a")
        a.add_transition(s2, s2, "b")
        a.add_transition(s2, s1, "a")

        # examples of strings that are accepted by the regular expression
        accepted, states, remaining = a.read_string("a b b b b b b b b b b b b b")

        assert accepted == True, f"Received: {accepted}, {states}, {remaining}"
        assert s2.id in states
        assert remaining == ""

        accepted, states, remaining = a.read_string("a b b b b b b a a b b b b b b b")

        assert accepted == True, f"Received: {accepted}, {states}, {remaining}"
        assert s2.id in states
        assert remaining == ""

        accepted, states, remaining = a.read_string("a b b b b b b a a b b b b b b b a a")

        assert accepted == True, f"Received: {accepted}, {states}, {remaining}"
        assert s2.id in states
        assert remaining == ""

        accepted, states, remaining = a.read_string("a")

        assert accepted == True, f"Received: {accepted}, {states}, {remaining}"
        assert s2.id in states
        assert remaining == ""

        # example of strings that are not accepted by the regular expression
        accepted, states, remaining = a.read_string("a a")

        assert accepted == False, f"Received: {accepted}, {states}, {remaining}"
        assert s1.id in states
        assert remaining == ""

        accepted, states, remaining = a.read_string("a a b b")

        assert accepted == False, f"Received: {accepted}, {states}, {remaining}"
        assert s1.id in states
        assert remaining == "b b"

        accepted, states, remaining = a.read_string("a b b b b b a a b a")

        assert accepted == False, f"Received: {accepted}, {states}, {remaining}"
        assert s1.id in states
        assert remaining == ""

        accepted, states, remaining = a.read_string("")

        assert accepted == False, f"Received: {accepted}, {states}, {remaining}"
        assert s1.id in states
        assert remaining == ""

        accepted, states, remaining = a.read_string("a b b b b b b c d e f")

        assert accepted == False, f"Received: {accepted}, {states}, {remaining}"
        assert s2.id in states
        assert remaining == "c d e f"

    def test_automaton_non_deterministic(self):

        s1 = nfa.State("s1")
        s2 = nfa.State("s2")
        s3 = nfa.State("s3")
        s4 = nfa.State("s4")
        s5 = nfa.State("s5")
        s6 = nfa.State("s6")
        s7 = nfa.State("s7")
        s8 = nfa.State("s8")
        s9 = nfa.State("s9")
        s10 = nfa.State("s10")
        s11 = nfa.State("s11")

        a = nfa.NFA()
        a.add_state(s1)
        a.add_state(s2)
        a.add_state(s3)
        a.add_state(s4)
        a.add_state(s5)
        a.add_state(s6)
        a.add_state(s7)
        a.add_state(s8, is_final=True)
        a.add_state(s9, is_final=True)
        a.add_state(s10, is_final=True)
        a.add_state(s11, is_final=True)

        # 1st level
        a.add_transition(s1, s2, "a")
        a.add_transition(s1, s3, "a")

        # 2nd level
        a.add_transition(s2, s4, "b")
        a.add_transition(s2, s5, "b")

        a.add_transition(s3, s6, "b")
        a.add_transition(s3, s7, "b")

        # 3rd level
        a.add_transition(s4, s8, "c")
        a.add_transition(s5, s9, "d")

        a.add_transition(s6, s10, "e")
        a.add_transition(s7, s11, "f")


        a.set_initial(s1)

        accepted, states, remaining = a.read_string("a b c")

        assert accepted == True, f"Received: {accepted}, {states}, {remaining}"
        assert s8.id in states, f"Received: {accepted}, {states}, {remaining}"
        assert remaining == "", f"Received: {accepted}, {states}, {remaining}"

    def test_automaton_with_epsilon(self):

        s1 = nfa.State("s1")
        s2 = nfa.State("s2")
        s3 = nfa.State("s3")
        s4 = nfa.State("s4")
        s5 = nfa.State("s5")
        s6 = nfa.State("s6")
        s7 = nfa.State("s7")
        s8 = nfa.State("s8")
        s9 = nfa.State("s9")
        s10 = nfa.State("s10")
        s11 = nfa.State("s11")

        a = nfa.NFA()
        a.add_state(s1)
        a.add_state(s2)
        a.add_state(s3)
        a.add_state(s4)
        a.add_state(s5)
        a.add_state(s6)
        a.add_state(s7)
        a.add_state(s8, is_final=True)
        a.add_state(s9, is_final=True)
        a.add_state(s10, is_final=True)
        a.add_state(s11, is_final=True)

        # 1st level
        a.add_transition(s1, s2, "a")
        a.add_transition(s1, s3, "a")

        # 2nd level
        a.add_transition(s2, s4, "b")
        a.add_transition(s2, s5) # epsilon transition

        a.add_transition(s3, s6, "b")
        a.add_transition(s3, s7) # epsilon transition

        # 3rd level
        a.add_transition(s4, s8, "c")
        a.add_transition(s5, s9, "d")

        a.add_transition(s6, s10, "e")
        a.add_transition(s7, s11, "f")


        a.set_initial(s1)

        accepted, states, remaining = a.read_string("a c")
        assert accepted == False
        assert s5.id in states
        assert s7.id in states
        assert remaining == "c"

        accepted, states, remaining = a.read_string("a d")
        assert accepted == True
        assert s9.id in states, f"Received: {accepted}, {states}, {remaining}"
        assert remaining == ""


class TestInputScanner(TestCase):

    def test_scan_empty_input(self):

        iscan = nfa.InputScanner("")
        
        assert iscan.pos == 0
        assert iscan.eof


    def test_scan_correct_input(self):

        iscan = nfa.InputScanner("foo fie fez")

        assert iscan.pos == 0
        assert not iscan.eof
        token = iscan.scan_input()
        assert token == "foo", f"Received: {token}"

        assert iscan.pos == 4
        assert not iscan.eof
        token = iscan.scan_input()
        assert token == "fie", f"Received: {token}"

        assert iscan.pos == 8
        assert not iscan.eof
        token = iscan.scan_input()
        assert token == "fez", f"Received: {token}"
        assert iscan.eof

        with self.assertRaises(Exception) as context:
            token = iscan.scan_input()


    def test_scan_tokens_with_spaces(self):

        input_str = "'foo fie' fez"
        iscan = nfa.InputScanner(input_str)

        assert iscan.pos == 0
        assert not iscan.eof
        token = iscan.scan_input()
        assert token == "foo fie", f"Received: {token}"

        assert iscan.pos == 10, f"Received: {iscan.pos}. Input: {input_str}"
        assert not iscan.eof
        token = iscan.scan_input()
        assert token == "fez", f"Received: {token}"
        assert iscan.eof

        with self.assertRaises(Exception) as context:
            # it should throw an exception for scanning the input after EOF
            token = iscan.scan_input()



class TestReiToNFA(TestCase):

    def test_base_case(self):

        r = rei.Symbol("foo")

        a = nfa.ReiToNFA(r)

        accepted, states, remaining = a.read_string("foo")
        assert accepted == True, f"Received: {accepted}, {states}, {remaining}"
        assert a.is_final(states)
        assert remaining == ""

        accepted, states, remaining = a.read_string("fie")
        assert accepted == False, f"Received: {accepted}, {states}, {remaining}"
        assert a.initial.id in states
        assert remaining == "fie"

        accepted, states, remaining = a.read_string("foo fie")
        assert accepted == False, f"Received: {accepted}, {states}, {remaining}"
        assert a.is_final(states)
        assert remaining == "fie"

        assert len(a.states) == 2
        assert len(a.final) == 1
        assert len(a.transitions) == 1
        assert a.transitions[0].source == a.initial
        assert a.transitions[0].target == a.final[0]
        assert a.transitions[0].label == "foo"

        print(f"NFA: {str(a)}")


    def test_union(self):

        r = rei.Union(rei.Conc(rei.Symbol("foo"), rei.Symbol("fie")), rei.Conc(rei.Symbol("zig"), rei.Symbol("zag")))

        a = nfa.ReiToNFA(r)

        accepted, states, remaining = a.read_string("foo fie")
        assert accepted == True, f"Received: {accepted}, {states}, {remaining}"
        assert a.is_final(states)
        assert remaining == ""

        accepted, states, remaining = a.read_string("zig zag")
        assert accepted == True, f"Received: {accepted}, {states}, {remaining}"
        assert a.is_final(states)
        assert remaining == ""

        accepted, states, remaining = a.read_string("foo fie zig")
        assert accepted == False, f"Received: {accepted}, {states}, {remaining}"
        assert a.is_final(states)
        assert remaining == "zig", f"Received: {remaining}"

        accepted, states, remaining = a.read_string("foo fie zig zag")
        assert accepted == False, f"Received: {accepted}, {states}, {remaining}"
        assert a.is_final(states)
        assert remaining == "zig zag", f"Received: {remaining}"



    def test_star(self):

        r = rei.Star(rei.Conc("foo", "fie"))

        a = nfa.ReiToNFA(r)

        accepted, states, remaining = a.read_string("")
        assert accepted == True, f"Received: {accepted}, {states}, {remaining}"
        assert a.is_final(states)
        assert remaining == ""

        accepted, states, remaining = a.read_string("foo fie")
        assert accepted == True, f"Received: {accepted}, {states}, {remaining}"
        assert a.is_final(states)
        assert remaining == ""

        accepted, states, remaining = a.read_string("foo fie foo fie foo fie foo fie")
        assert accepted == True, f"Received: {accepted}, {states}, {remaining}"
        assert a.is_final(states)
        assert remaining == ""

        accepted, states, remaining = a.read_string("foo fie foo fie foo")
        assert accepted == False, f"Received: {accepted}, {states}, {remaining}"
        assert not a.is_final(states)
        assert remaining == ""

        accepted, states, remaining = a.read_string("foo fie foo fie foo baz")
        assert accepted == False, f"Received: {accepted}, {states}, {remaining}"
        assert not a.is_final(states)
        assert remaining == "baz"

    def test_union_star(self):

        r = rei.Star(rei.Union(rei.Conc("foo", "fie"), rei.Conc("zig", "zag")))

        a = nfa.ReiToNFA(r)

        accepted, states, remaining = a.read_string("")
        assert accepted == True, f"Received: {accepted}, {states}, {remaining}"
        assert a.is_final(states)
        assert remaining == ""

        accepted, states, remaining = a.read_string("foo fie")
        assert accepted == True, f"Received: {accepted}, {states}, {remaining}"
        assert a.is_final(states)
        assert remaining == ""

        accepted, states, remaining = a.read_string("zig zag")
        assert accepted == True, f"Received: {accepted}, {states}, {remaining}"
        assert a.is_final(states)
        assert remaining == ""

        accepted, states, remaining = a.read_string("foo fie zig zag")
        assert accepted == True, f"Received: {accepted}, {states}, {remaining}"
        assert a.is_final(states)
        assert remaining == ""

        accepted, states, remaining = a.read_string("foo fie zig zag zig zag")
        assert accepted == True, f"Received: {accepted}, {states}, {remaining}"
        assert a.is_final(states)
        assert remaining == ""

        accepted, states, remaining = a.read_string("foo fie zig fie")
        assert accepted == False, f"Received: {accepted}, {states}, {remaining}"
        assert not a.is_final(states)
        assert remaining == "fie"


        accepted, states, remaining = a.read_string("foo fie zig")
        assert accepted == False, f"Received: {accepted}, {states}, {remaining}"
        assert not a.is_final(states)
        assert remaining == ""

        accepted, states, remaining = a.read_string("foo fie big fie")
        assert accepted == False, f"Received: {accepted}, {states}, {remaining}"
        assert a.is_final(states)
        assert remaining == "big fie"

    def test_union_star_nondeterminism(self):

        r = rei.Conc(rei.Star(rei.Union(
                        rei.Conc("foo", "fie"), 
                        rei.Conc("foo", "fie", "fez"))), 
                    "zog")

        a = nfa.ReiToNFA(r)


        accepted, state, remaining = a.read_string("")
        assert accepted == False, f"Received: {accepted}, {state}, {remaining}"
        assert not a.is_final(state)
        assert remaining == ""


        accepted, state, remaining = a.read_string("foo fie zog")
        assert accepted == True, f"Received: {accepted}, {state}, {remaining}"
        assert a.is_final(state)
        assert remaining == ""


        accepted, state, remaining = a.read_string("foo fie fez zog")
        assert accepted == True, f"Received: {accepted}, {state}, {remaining}"
        assert a.is_final(state)
        assert remaining == ""


        accepted, state, remaining = a.read_string("zog")
        assert accepted == True, f"Received: {accepted}, {state}, {remaining}"
        assert a.is_final(state)
        assert remaining == ""


        accepted, state, remaining = a.read_string("foo zog")
        assert accepted == False, f"Received: {accepted}, {state}, {remaining}"
        assert not a.is_final(state)
        assert remaining == "zog", f"Received: {remaining}"


    def test_par(self):

        r = rei.Par(rei.Conc("foo", "fie", "fez"), rei.Conc("zog", "zip"))

        a = nfa.ReiToNFA(r)

        accepted, state, remaining = a.read_string("")
        assert accepted == False, f"Received: {accepted}, {state}, {remaining}"
        assert not a.is_final(state)
        assert remaining == ""

        accepted, state, remaining = a.read_string("foo fie fez")
        assert accepted == False, f"Received: {accepted}, {state}, {remaining}"
        assert not a.is_final(state)
        assert remaining == ""

        accepted, state, remaining = a.read_string("zog zip")
        assert accepted == False, f"Received: {accepted}, {state}, {remaining}"
        assert not a.is_final(state)
        assert remaining == ""

        accepted, state, remaining = a.read_string("foo fie fez zog zip")
        assert accepted == True, f"Received: {accepted}, {state}, {remaining}"
        assert a.is_final(state)
        assert remaining == ""
        
        accepted, state, remaining = a.read_string("foo zog fie fez zip")
        assert accepted == True, f"Received: {accepted}, {state}, {remaining}"
        assert a.is_final(state)
        assert remaining == ""
        
        accepted, state, remaining = a.read_string("zog zip foo fie fez")
        assert accepted == True, f"Received: {accepted}, {state}, {remaining}"
        assert a.is_final(state)
        assert remaining == ""
        
        accepted, state, remaining = a.read_string("zip zog foo fie fez")
        assert accepted == False, f"Received: {accepted}, {state}, {remaining}"
        assert not a.is_final(state)
        assert remaining == "zip zog foo fie fez"
        

class TestChoToNFA(TestCase):

    def setUp(self):

        choreographies = [
            ("diagram", "diagram.bpmn", ),
            ("diagram_minimal", "diagram_minimal.bpmn"),
            ("diagram_basic", "diagram_basic.bpmn"),
            ("diagram_gateways", "diagram_gateways.bpmn", ),
            ("diagram_gateways_mismatch", "diagram_gateways_mismatch.bpmn", ),
            ("diagram_gateways_dangling", "diagram_gateways_dangling.bpmn", ),
            ("diagram_gateways_nested", "diagram_gateways_nested.bpmn", ),
            ("diagram_gateways_nested_intermediate", "diagram_gateways_nested_with_intermediate_task.bpmn", ),
            ("diagram_gateways_nested_inclusive", "diagram_gateways_nested_inclusive.bpmn", ),
            ("diagram_gateways_nested_dangling", "diagram_gateways_nested_dangling.bpmn", ),

        ]

        for name, filename in choreographies:
            c:Choreography = Choreography()
            c.name = name
            c.resource = os.path.join(settings.MEDIA_ROOT, filename)
            c.save()

    def test_diagram_minimal(self):
        
        c:Choreography = Choreography.objects.get(name="diagram_minimal")

        # r, match = rei.ChoToRei(c)
        # a = nfa.ReiToNFA(r)
        a = c.to_nfa()

        accepted, state, remaining = a.read_string("")
        assert accepted == True, f"Received: {accepted}, State: {state}, Remaining: {remaining}"
        assert a.is_final(state)
        assert remaining == ""

        accepted, state, remaining = a.read_string("foo fie")
        assert accepted == False, f"Received: {accepted}, State: {state}, Remaining: {remaining}"
        assert a.is_final(state)
        assert remaining == "foo fie"


    def test_diagram_basic(self):
        
        c:Choreography = Choreography.objects.get(name="diagram_basic")

        # r, match = rei.ChoToRei(c)
        # a = nfa.ReiToNFA(r)
        a = c.to_nfa()

        accepted, state, remaining = a.read_string("")
        assert accepted == True, f"Received: {accepted}, State: {state}, Remaining: {remaining}"
        assert a.is_final(state)
        assert remaining == ""

        accepted, state, remaining = a.read_string("foo fie")
        assert accepted == False, f"Received: {accepted}, State: {state}, Remaining: {remaining}"
        assert a.is_final(state)
        assert remaining == "foo fie"

    
    def test_diagram(self):
        
        c:Choreography = Choreography.objects.get(name="diagram")

        # r, match = rei.ChoToRei(c, rei.render_receive)
        # a = nfa.ReiToNFA(r)
        a = c.to_nfa()

        accepted, state, remaining = a.read_string("Pizza_Place?pizza_order Delivery_Boy?Message_1mi4idx Customer?pizza")
        assert accepted == True, f"Received: {accepted}, State: {state}, Remaining: {remaining}"
        assert a.is_final(state)
        assert remaining == ""

        accepted, state, remaining = a.read_string("Pizza_Place?pizza_order Customer?pizza")
        assert accepted == False, f"Received: {accepted}, State: {state}, Remaining: {remaining}"
        assert not a.is_final(state)
        assert remaining == "Customer?pizza"

    def test_nested(self):
        
        c:Choreography = Choreography.objects.get(name="diagram_gateways_nested")

        a = c.to_nfa()
        # r, match = rei.ChoToRei(c, rei.render_receive)
        # a = nfa.ReiToNFA(r)
# '^Pizza_Place?pizza_order (Pizza_Place?Message_0rkgt7n | Delivery_Boy?Message_1mi4idx Customer?pizza (Delivery_Boy?Message_0oddh8c Customer?Message_1fakyw2 & Delivery_Boy?Message_08qtv9f))$'

        accepted, state, remaining = a.read_string("Pizza_Place?pizza_order Pizza_Place?Message_0rkgt7n")
        assert accepted == True, f"Received: {accepted}, State: {state}, Remaining: {remaining}"
        assert a.is_final(state)
        assert remaining == ""

        accepted, state, remaining = a.read_string("Pizza_Place?pizza_order Delivery_Boy?Message_1mi4idx Customer?pizza Delivery_Boy?Message_0oddh8c Delivery_Boy?Message_08qtv9f Customer?Message_1fakyw2")
        assert accepted == True, f"Received: {accepted}, State: {state}, Remaining: {remaining}"
        assert a.is_final(state)
        assert remaining == ""

        # the example below is missing a message expected by the parallel gateway (viz. Delivery_Boy?Message_0oddh8c)
        accepted, state, remaining = a.read_string("Pizza_Place?pizza_order Delivery_Boy?Message_1mi4idx Customer?pizza Delivery_Boy?Message_0oddh8c Customer?Message_1fakyw2")
        assert accepted == False, f"Received: {accepted}, State: {state}, Remaining: {remaining}"
        assert not a.is_final(state)
        assert remaining == ""


class TestEnforcer(TestCase):

    def setUp(self):

        choreographies = [
            ("diagram", "diagram.bpmn", ),
            ("diagram_minimal", "diagram_minimal.bpmn"),
            ("diagram_basic", "diagram_basic.bpmn"),
            ("diagram_gateways", "diagram_gateways.bpmn", ),
            ("diagram_gateways_mismatch", "diagram_gateways_mismatch.bpmn", ),
            ("diagram_gateways_dangling", "diagram_gateways_dangling.bpmn", ),
            ("diagram_gateways_nested", "diagram_gateways_nested.bpmn", ),
            ("diagram_gateways_nested_intermediate", "diagram_gateways_nested_with_intermediate_task.bpmn", ),
            ("diagram_gateways_nested_inclusive", "diagram_gateways_nested_inclusive.bpmn", ),
            ("diagram_gateways_nested_dangling", "diagram_gateways_nested_dangling.bpmn", ),

        ]

        for name, filename in choreographies:
            c:Choreography = Choreography()
            c.name = name
            c.resource = os.path.join(settings.MEDIA_ROOT, filename)
            c.save()

    def test_initialization(self):

        c:Choreography = Choreography.objects.get(name="diagram")
        n = c.to_nfa()

        e = Enforcer(n)

        assert not e.buffer, f"Expected empty buffer, received: {self.buffer}"
        assert e.buffer_empty

        with self.assertRaises(Exception) as context:
            # an exception is expected if initializing the Enforcer without an NFA
            e1 = Enforcer(None)


    def test_buffer(self):

        c:Choreography = Choreography.objects.get(name="diagram")
        n = c.to_nfa()

        e = Enforcer(n)

        e.buffer_add("a1", "m1")
        
        assert not e.buffer_empty()

        e.buffer_add("a1", "m1")
        e.buffer_add("a1", "m2")
        e.buffer_add("a2", "m3")

        assert e.buffer_has_message(actor="a1")
        assert e.buffer_has_message(message="m1")
        assert e.buffer_has_message(message="m3")

        assert not e.buffer_has_message(message="a3")
        assert not e.buffer_has_message(actor="a2", message="m1")
        assert e.buffer_has_message(actor="a1", message="m2")
        
        assert e.buffer_has_message(actor="a1", message="m1")

        # remove first copy of a1?m1
        e.buffer_remove("a1","m1")

        assert e.buffer_has_message(actor="a1", message="m1")

        # remove second copy of a1?m1
        e.buffer_remove("a1","m1")

        assert not e.buffer_has_message(actor="a1", message="m1")


        assert not e.buffer_empty()

        e.buffer_remove("a1", "m2")
        e.buffer_remove("a2", "m3")

        assert e.buffer_empty()

        with self.assertRaises(Exception) as context:
            e.buffer_remove("a1", "m1")

    def test_process_receive(self):

        c:Choreography = Choreography.objects.get(name="diagram")
        n = c.to_nfa()

        e = Enforcer(n)

        # step 1

        s1 = e.curr_states

        in_event = "Pizza_Place?pizza_order"
        out_event = e.process_input(in_event)

        s2 = e.curr_states


        assert out_event == in_event, f"Expected {in_event}. Received: {out_event}"
        assert s1 != s2

        # step 2 (sending something not related to the choreography)

        in_event = "Pizza_Place!foo_fie"
        out_event = e.process_input(in_event)

        assert out_event == in_event, f"Expected {in_event}. Received: {out_event}"
        assert e.curr_states == s2

        # step 2 (receiving the expected message in the choreography)

        in_event = "Delivery_Boy?Message_1mi4idx"
        out_event = e.process_input(in_event)

        assert out_event == in_event, f"Expected {in_event}. Received: {out_event}"
        assert e.curr_states != s2

        # step 3 (receiving another choreography message)
        s2 = e.curr_states

        in_event = "Customer?pizza"
        out_event = e.process_input(in_event)

        assert out_event == in_event, f"Expected {in_event}. Received: {out_event}"
        assert e.curr_states != s2

        # step 3 (sending the expected choreography message)
        s2 = e.curr_states
        in_event = "Delivery_Boy!pizza"
        out_event = e.process_input(in_event)

        assert out_event == in_event, f"Expected {in_event}. Received: {out_event}"
        assert e.curr_states == s2

    def test_process_receive_delayed(self):

        c:Choreography = Choreography.objects.get(name="diagram")
        n = c.to_nfa()

        e = Enforcer(n)

        # step 1

        s1 = e.curr_states

        in_event = in_event_first = "Customer?pizza"
        out_event = e.process_input(in_event)

        assert out_event == ""
        assert e.curr_states == s1

        in_event = "Pizza_Place?pizza_order"
        out_event = e.process_input(in_event)

        assert out_event == in_event
        assert e.curr_states != s1

        s1 = e.curr_states

        in_event = "Delivery_Boy?Message_1mi4idx"
        out_event = e.process_input(in_event)

        assert out_event == in_event
        assert e.curr_states != s1

        s1 = e.curr_states
        out_event = e.process_check()

        assert out_event == in_event_first
        assert e.curr_states != s1


    # TODO restore this test
    # def test_reordering(self):

    #     c:Choreography = Choreography.objects.get(name="diagram")
    #     n = c.to_nfa()

    #     e = Enforcer(n)

    #     in_events = "Customer?pizza Pizza_Place?pizza_order Delivery_Boy?Message_1mi4idx"
    #     out_events = "Pizza_Place?pizza_order Delivery_Boy?Message_1mi4idx Customer?pizza"

    #     res = e.process_input(in_events)

    #     # assert res == out_events
    #     assert e.nfa.is_final(e.curr_states)


class TestContracts(TestCase):

    def setUp(self):

        choreographies = [
            ("diagram", "diagram.bpmn", ),
            ("diagram_minimal", "diagram_minimal.bpmn"),
            ("diagram_basic", "diagram_basic.bpmn"),
            ("diagram_gateways", "diagram_gateways.bpmn", ),
            ("diagram_gateways_mismatch", "diagram_gateways_mismatch.bpmn", ),
            ("diagram_gateways_dangling", "diagram_gateways_dangling.bpmn", ),
            ("diagram_gateways_nested", "diagram_gateways_nested.bpmn", ),
            ("diagram_gateways_nested_intermediate", "diagram_gateways_nested_with_intermediate_task.bpmn", ),
            ("diagram_gateways_nested_inclusive", "diagram_gateways_nested_inclusive.bpmn", ),
            ("diagram_gateways_nested_dangling", "diagram_gateways_nested_dangling.bpmn", ),

        ]

        for name, filename in choreographies:
            c:Choreography = Choreography()
            c.name = name
            c.resource = os.path.join(settings.MEDIA_ROOT, filename)
            c.save()


    def test_variables(self):

        v = contracts.Variable("foo", "uint8")
        
        assert v.name == "foo"
        assert v.type == "uint8"
        assert v.compile() == "uint8 foo"


    def test_functions(self):

        f = contracts.Function("foo", [], "return 10;", "public")

        assert f.name == "foo"
        assert len(f.parameters) == 0
        assert f.visibility == "public"

        f_compiled = f.compile()
        assert "function foo" in f_compiled
        assert f.visibility in f_compiled
        assert f.body in f_compiled

    

        

        
