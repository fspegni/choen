from django.test import TestCase
from mpst import *

class MPSTTestCase(TestCase):

    def test_create_operators(self):

        v1 = StateVar("v1")
        v2 = StateVar("v2")
        j = Join([v1,v2])
        f = Fork([v1,v2])
        m = Merge([v1,v2])
        c = Choice([v1,v2])

        msg = MsgExc("a1", "a2", "my_msg", 3)

        str(v1)
        str(v2)
        str(j)
        str(f)
        str(m)
        str(c)

        str(msg)

    def test_compute_zero_participants(self):

        v1 = StateVar("v1")
        v2 = StateVar("v2")
        j = Join([v1,v2])
        f = Join([v1,v2])
        m = Join([v1,v2])

        self.assertTrue(len(j.participants) == 0)
        self.assertTrue(len(f.participants) == 0)
        self.assertTrue(len(m.participants) == 0)

    def test_messages_add_participants(self):

        v1 = StateVar("v1")
        v2 = StateVar("v2")

        msg = MsgExc("a1", "a2", "my_msg", 3)

        c = Concat(msg, v1)

        self.assertEqual(len(msg.participants), 2)
        self.assertEqual(len(c.participants), 2)

    def test_messages_sender_receiver_must_differ(self):

        v1 = StateVar("v1")
        with self.assertRaises(Exception) as context:
            msg = MsgExc("a1", "a1", "my_msg", 3)

        self.assertTrue("cannot be the same" in str(context.exception))


    def test_transforms_basic(self):

        v1 = StateVar("v1")
        v2 = StateVar("v2")
        v3 = StateVar("v3")
        v4 = StateVar("v4")

        f = Fork([v2,v3])
        j = Join([v2,v3])

        t_f = Transform(v1, f)
        t_j = Transform(j, v4)

        str(t_f)
        str(t_j)

        #breakpoint()

        self.assertEqual(len(t_f.participants), 0)
        self.assertEqual(len(t_j.participants), 0)


    def test_transforms_advanced(self):

        v1 = StateVar("v1")
        v2 = StateVar("v2")
        v3 = StateVar("v3")

        me1 = MsgExc("a", "b", "foo", 3)
        me2 = MsgExc("a", "b", "foo", 3)

        c1 = Concat(me1, v2)
        c2 = Concat(me2, v3)

        v4 = StateVar("v4")

        f = Fork([c1,c2])
        j = Join([v2,v3])

        t_f = Transform(v1, f)
        t_j = Transform(j, v4)

        str(t_f)
        str(t_j)

        #breakpoint()

        self.assertEqual(len(t_f.participants), 2)
        self.assertEqual(len(t_j.participants), 0)
