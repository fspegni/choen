from django.test import TestCase
from mpst.models import *


class MPSTTestCase(TestCase):

    def test_create_operators(self):

        v1 = StateVar("v1")
        v2 = StateVar("v2")
        j = Join(v1,v2)
        f = Fork(v1,v2)
        m = Merge(v1,v2)
        c = Choice(v1,v2)

        msg = MsgExc("a1", "a2", "my_msg", int)

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
        j = Join(v1,v2)
        f = Join(v1,v2)
        m = Join(v1,v2)

        self.assertTrue(len(j.participants) == 0)
        self.assertTrue(len(f.participants) == 0)
        self.assertTrue(len(m.participants) == 0)

    def test_messages_add_participants(self):

        v1 = StateVar("v1")
        v2 = StateVar("v2")

        msg = MsgExc("a1", "a2", "my_msg", int)

        c = Concat(msg, v1)

        self.assertEqual(len(msg.participants), 2)
        self.assertEqual(len(c.participants), 2)

    def test_messages_sender_receiver_must_differ(self):

        v1 = StateVar("v1")
        with self.assertRaises(Exception) as context:
            msg = MsgExc("a1", "a1", "my_msg", str)

        self.assertTrue("cannot be the same" in str(context.exception))


    def test_transforms_basic(self):

        v1 = StateVar("v1")
        v2 = StateVar("v2")
        v3 = StateVar("v3")
        v4 = StateVar("v4")

        f = Fork(v2,v3)
        j = Join(v2,v3)

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

        me1 = MsgExc("a", "b", "foo", str)
        me2 = MsgExc("a", "b", "fie", bool)

        c1 = Concat(me1, v2)
        c2 = Concat(me2, v3)

        v4 = StateVar("v4")

        f = Fork(c1,c2)
        j = Join(v2,v3)

        t_f = Transform(v1, f)
        t_j = Transform(j, v4)

        str(t_f)
        str(t_j)

        #breakpoint()

        self.assertEqual(len(t_f.participants), 2)
        self.assertEqual(len(t_j.participants), 0)


    def test_model_message_payload(self):

        # message with payload of type integer
        me1 = MsgExc("a", "b", "foo", int)

        str(me1)
        
        # message with payload of type string
        me2 = MsgExc("a", "b", "foo", str)

        str(me2)
    
        # message with payload of combined type
        me3 = MsgExc("a", "b", "foo", (str, int))

        str(me3)       


    def test_global_type_with_no_transforms(self):

        #breakpoint()
        v1 = StateVar("v1")
        g = GlobalType(v1)

        self.assertTrue(isinstance(g.transforms, list))

        self.assertEqual(len(g.transforms), 0)


    def test_global_type_with_initial_transforms(self):

        v1 = StateVar("v1")
        v2 = StateVar("v2")
        v3 = StateVar("v3")

        me1 = MsgExc("a", "b", "foo", str)
        me2 = MsgExc("a", "b", "fie", bool)

        c1 = Concat(me1, v2)
        c2 = Concat(me2, v3)

        v4 = StateVar("v4")

        f = Fork(c1,c2)
        j = Join(v2,v3)

        t_f = Transform(v1, f)
        t_j = Transform(j, v4)

        g = GlobalType(v1, [t_f, t_j])

        self.assertTrue(isinstance(g.transforms, list))
        self.assertEqual(len(g.transforms), 2)


    def test_global_types_example_1(self):

        x0 = StateVar("x0")
        x1 = StateVar("x1")

        m1 = MsgExc("Alice", "Bob", "Msg", (int, bool))

        t1 = Transform(x0, Concat(m1, x1))

        #breakpoint()
        t2 = Transform(x1, End())
        
        #breakpoint()
        g = GlobalType(x0, [t1, t2])
        str(g)

    def test_global_types_example_2(self):

        x0 = StateVar("x0")
        x1 = StateVar("x1")
        x2 = StateVar("x2")
        x3 = StateVar("x3")
        x4 = StateVar("x4")
        x5 = StateVar("x5")

        m1 = MsgExc("Alice", "Bob", "Book", str)
        m2 = MsgExc("Alice", "Bob", "Film", str)

        t1 = Transform(x0, Choice(x1, x2))
        t2 = Transform(x1, Concat(m1, x3))
        t3 = Transform(x2, Concat(m2, x4))
        t4 = Transform(Merge(x3, x4), x5)
        t5 = Transform(x5, End())

        #breakpoint()
        g = GlobalType(x0, [t1, t2, t3, t4, t5])
        str(g)



    def test_globa_types_json_export(self):
        x0 = StateVar("x0")
        x1 = StateVar("x1")

        m1 = MsgExc("Alice", "Bob", "Msg", (int, bool))

        t1 = Transform(x0, Concat(m1, x1))

        #breakpoint()
        t2 = Transform(x1, End())
        
        #breakpoint()
        g = GlobalType(x0, [t1, t2])
        j = g.to_json()

        self.assertTrue(isinstance(j, dict))

        self.assertTrue("type" in j)
        self.assertTrue(j["type"] == "GlobalType")

        self.assertTrue("initial" in j)
        self.assertTrue(j["initial"] == x0.to_json())

        self.assertTrue("transforms" in j)
        self.assertEqual(len(j["transforms"]), 2)

        # to_json() can be serialized
        import json
        self.assertTrue(isinstance(json.dumps(j), str))


    def test_compute_participants(self):

        x0 = StateVar("x0")
        x1 = StateVar("x1")
        x2 = StateVar("x2")
        x3 = StateVar("x3")
        x4 = StateVar("x4")

        m1 = MsgExc("Alice", "Bob", "Msg", (int, bool))
        m2 = MsgExc("Bob", "Charlie", "Msg", (int, bool))
        m3 = MsgExc("Charlie", "Dan", "Msg", (int, bool))

        t1 = Transform(x0, Concat(m1, x1))
        t2 = Transform(x1, Concat(m2, x2))
        t3 = Transform(x2, Concat(m3, x3))
        t4 = Transform(x3, End())

        #breakpoint()
        g = GlobalType(x0, [t1, t2, t3, t4])
 
        self.assertEqual(g.participants, set(["Alice", "Bob", "Charlie", "Dan"]))


    def test_get_threads_simple(self):

        x0 = StateVar("x0")
        x1 = StateVar("x1")
        x2 = StateVar("x2")
        x3 = StateVar("x3")
        x4 = StateVar("x4")

        m1 = MsgExc("Alice", "Bob", "Msg", (int, bool))
        m2 = MsgExc("Bob", "Charlie", "Msg", (int, bool))
        m3 = MsgExc("Charlie", "Dan", "Msg", (int, bool))

        t1 = Transform(x0, Concat(m1, x1))
        t2 = Transform(x1, Concat(m2, x2))
        t3 = Transform(x2, Concat(m3, x3))
        t4 = Transform(x3, End())

        #breakpoint()
        g = GlobalType(x0, [t1, t2, t3, t4])
 
        #breakpoint()
        self.assertEqual(len(g.get_thread(x0)), 4)
        self.assertEqual(len(g.get_thread("x0")), 4)
        self.assertEqual(len(g.get_thread(x3)), 1)
        self.assertEqual(len(g.get_thread(x4)), 0)

 
    def test_get_threads_with_structure(self):
 
        # prepare more complex structure, from example 2
        x0 = StateVar("x0")
        x1 = StateVar("x1")
        x2 = StateVar("x2")
        x3 = StateVar("x3")
        x4 = StateVar("x4")
        x5 = StateVar("x5")

        m1 = MsgExc("Alice", "Bob", "Book", str)
        m2 = MsgExc("Alice", "Bob", "Film", str)

        t1 = Transform(x0, Choice(x1, x2))
        t2 = Transform(x1, Concat(m1, x3))
        t3 = Transform(x2, Concat(m2, x4))
        t4 = Transform(Merge(x3, x4), x5)
        t5 = Transform(x5, End())

        #breakpoint()
        g = GlobalType(x0, [t1, t2, t3, t4, t5])
      
        # assert properties of threads

        self.assertEqual(len(g.get_thread(x0)), 1)
        #breakpoint()
        self.assertEqual(len(g.get_thread(x1)), 2)
        self.assertEqual(len(g.get_thread(x2)), 2)
        self.assertEqual(len(g.get_thread(x5)), 1)


    def test_state_vars_simple(self):

        # prepare more complex structure, from example 2
        x0 = StateVar("x0")
        x1 = StateVar("x1")
        x2 = StateVar("x2")
        x3 = StateVar("x3")
        x4 = StateVar("x4")
        x5 = StateVar("x5")

        m1 = MsgExc("Alice", "Bob", "Book", str)
        m2 = MsgExc("Alice", "Bob", "Film", str)

        t1 = Transform(x0, Choice(x1, x2))
        t2 = Transform(x1, Concat(m1, x3))
        t3 = Transform(x2, Concat(m2, x4))
        t4 = Transform(Merge(x3, x4), x5)
        t5 = Transform(x5, End())

        self.assertEqual(t1.lhs_vars, set([x0]))
        self.assertEqual(t1.rhs_vars, set([x1,x2]))

        self.assertEqual(t2.lhs_vars, set([x1]))
        self.assertEqual(t2.rhs_vars, set([x3]))

        self.assertEqual(t3.lhs_vars, set([x2]))
        self.assertEqual(t3.rhs_vars, set([x4]))

        self.assertEqual(t4.lhs_vars, set([x3,x4]))
        self.assertEqual(t4.rhs_vars, set([x5]))

        self.assertEqual(t5.lhs_vars, set([x5]))
        self.assertEqual(t5.rhs_vars, set([]))


    def test_replace_existing_var(self):

        # prepare more complex structure, from example 2
        x0 = StateVar("x0")
        x1 = StateVar("x1")
        x2 = StateVar("x2")
        x3 = StateVar("x3")
        x4 = StateVar("x4")
        x5 = StateVar("x5")

        m1 = MsgExc("Alice", "Bob", "Book", str)
        m2 = MsgExc("Alice", "Bob", "Film", str)

        t1 = Transform(x0, Choice(x1, x2))
        t2 = Transform(x1, Concat(m1, x3))
        t3 = Transform(x2, Concat(m2, x4))
        t4 = Transform(Merge(x3, x4), x5)
        t5 = Transform(x5, End())

        #breakpoint()
        g = GlobalType(x0, [t1, t2, t3, t4, t5])
 

        # t1
        self.assertTrue(x4 not in t1.rhs_vars)
        self.assertTrue(x2 in t1.rhs_vars)
        t1.replace_var(x2, x4)
        self.assertTrue(x4 in t1.rhs_vars)
        self.assertTrue(x2 not in t1.rhs_vars)

        # t2
        self.assertTrue(x4 not in t2.rhs_vars)
        self.assertTrue(x3 in t2.rhs_vars)
        t2.replace_var(x3, x4)
        self.assertTrue(x4 in t2.rhs_vars)
        self.assertTrue(x3 not in t2.rhs_vars)

        # t3
        self.assertTrue(x2 not in t3.rhs_vars)
        self.assertTrue(x4 in t3.rhs_vars)
        t3.replace_var(x4, x2)
        self.assertTrue(x2 in t3.rhs_vars)
        self.assertTrue(x4 not in t3.rhs_vars)

        # t4
        self.assertTrue(x2 not in t4.rhs_vars)
        self.assertTrue(x5 in t4.rhs_vars)
        t4.replace_var(x5, x2)
        self.assertTrue(x2 in t4.rhs_vars)
        self.assertTrue(x5 not in t4.rhs_vars)

        # t5 : no state variable to replace
        self.assertTrue(x2 not in t5.rhs_vars)
        t5.replace_var(x2, x4)
        self.assertTrue(x2 not in t5.rhs_vars)


    def test_example_2_is_well_formed(self):

        x0 = StateVar("x0")
        x1 = StateVar("x1")
        x2 = StateVar("x2")
        x3 = StateVar("x3")
        x4 = StateVar("x4")
        x5 = StateVar("x5")

        m1 = MsgExc("Alice", "Bob", "Book", str)
        m2 = MsgExc("Alice", "Bob", "Film", str)

        t1 = Transform(x0, Choice(x1, x2))
        t2 = Transform(x1, Concat(m1, x3))
        t3 = Transform(x2, Concat(m2, x4))
        t4 = Transform(Merge(x3, x4), x5)
        t5 = Transform(x5, End())

        #breakpoint()
        g = GlobalType(x0, [t1, t2, t3, t4, t5])

        #breakpoint()
        g.check_wellformed()



    def test_dead_end_is_not_well_formed(self):

        x0 = StateVar("x0")
        x1 = StateVar("x1")
        x2 = StateVar("x2")
        x3 = StateVar("x3")
        x4 = StateVar("x4")
        x5 = StateVar("x5")
        x6 = StateVar("x6")

        m1 = MsgExc("Alice", "Bob", "Book", str)
        m2 = MsgExc("Alice", "Bob", "Film", str)

        t1 = Transform(x0, Choice(x1, x2))
        t2 = Transform(x1, Concat(m1, x3))
        t3 = Transform(x2, Concat(m2, x4))
        t4 = Transform(Merge(x3, x4), x6) # NB here we go to a dead end
        t5 = Transform(x5, End()) # NB this is never reached

        #breakpoint()
        g = GlobalType(x0, [t1, t2, t3, t4, t5])

        #breakpoint()

        with self.assertRaises(Exception) as context:
            # an exception is expected, because rules do not allow to reach the end state
            g.check_wellformed()

        self.assertTrue("end state is not reachable" in str(context.exception))



    def test_simplify_linear(self):

        x0 = StateVar("x0")
        x1 = StateVar("x1")
        x2 = StateVar("x2")
        x3 = StateVar("x3")
        x4 = StateVar("x4")
        x5 = StateVar("x5")

        m1 = MsgExc("Alice", "Bob", "Book", str)
        m2 = MsgExc("Alice", "Bob", "Film", str)

        t1 = Transform(x0, Concat(m1, x1))
        t2 = Transform(x1, Concat(m2, x2))
        t3 = Transform(x2, End())

        g = GlobalType(x0, [t1, t2, t3 ])

        #breakpoint()
        g1 = g.simplify()

        self.assertEqual(g1.initial, x2)
        self.assertEqual(len(g1.transforms), 1)
        self.assertTrue(isinstance(g1.transforms[0].rhs, End))
        self.assertEqual(g1.transforms[0].lhs, x2)


    def test_simplify_join_fork_par_1(self):

        x0 = StateVar("x0")
        x1 = StateVar("x1")
        x2 = StateVar("x2")
        x3 = StateVar("x3")
        x4 = StateVar("x4")
        x5 = StateVar("x5")

        m1 = MsgExc("Alice", "Bob", "Book", str)
        m2 = MsgExc("Alice", "Bob", "Film", str)

        t1 = Transform(x0, Fork(x1, x2))
        t2 = Transform(x1, Concat(m1, x3))
        t3 = Transform(x2, Concat(m2, x4))
        t4 = Transform(Join(x3, x4), x5)
        t5 = Transform(x5, End())

        g = GlobalType(x0, [t1, t2, t3, t4, t5 ])

        #breakpoint()
        g1 = g.simplify()

        self.assertEqual(g1.initial, x5)
        self.assertEqual(len(g1.transforms), 1)
        self.assertTrue(isinstance(g1.transforms[0].rhs, End))
        self.assertEqual(g1.transforms[0].lhs, x5)


    def test_simplify_join_fork_par_1_commutativity_1(self):

        x0 = StateVar("x0")
        x1 = StateVar("x1")
        x2 = StateVar("x2")
        x3 = StateVar("x3")
        x4 = StateVar("x4")
        x5 = StateVar("x5")

        m1 = MsgExc("Alice", "Bob", "Book", str)
        m2 = MsgExc("Alice", "Bob", "Film", str)

        t1 = Transform(x0, Fork(x2, x1)) # NB changed order her
        t2 = Transform(x1, Concat(m1, x3))
        t3 = Transform(x2, Concat(m2, x4))
        t4 = Transform(Join(x3, x4), x5)
        t5 = Transform(x5, End())

        g = GlobalType(x0, [t1, t2, t3, t4, t5 ])

        #breakpoint()
        g1 = g.simplify()

        self.assertEqual(g1.initial, x5)
        self.assertEqual(len(g1.transforms), 1)
        self.assertTrue(isinstance(g1.transforms[0].rhs, End))
        self.assertEqual(g1.transforms[0].lhs, x5)


    def test_simplify_join_fork_par_1_commutativity_2(self):

        x0 = StateVar("x0")
        x1 = StateVar("x1")
        x2 = StateVar("x2")
        x3 = StateVar("x3")
        x4 = StateVar("x4")
        x5 = StateVar("x5")

        m1 = MsgExc("Alice", "Bob", "Book", str)
        m2 = MsgExc("Alice", "Bob", "Film", str)

        t1 = Transform(x0, Fork(x2, x1)) # NB changed order here
        t2 = Transform(x1, Concat(m1, x3))
        t3 = Transform(x2, Concat(m2, x4))
        t4 = Transform(Join(x4, x3), x5) # NB changed order here
        t5 = Transform(x5, End())

        g = GlobalType(x0, [t1, t2, t3, t4, t5 ])

        #breakpoint()
        g1 = g.simplify()

        self.assertEqual(g1.initial, x5)
        self.assertEqual(len(g1.transforms), 1)
        self.assertTrue(isinstance(g1.transforms[0].rhs, End))
        self.assertEqual(g1.transforms[0].lhs, x5)


    def test_simplify_join_fork_par_1_commutativity_2(self):

        x0 = StateVar("x0")
        x1 = StateVar("x1")
        x2 = StateVar("x2")
        x3 = StateVar("x3")
        x4 = StateVar("x4")
        x5 = StateVar("x5")

        m1 = MsgExc("Alice", "Bob", "Book", str)
        m2 = MsgExc("Alice", "Bob", "Film", str)

        t1 = Transform(x0, Fork(x1, x2))
        t2 = Transform(x1, Concat(m1, x3))
        t3 = Transform(x2, Concat(m2, x4))
        t4 = Transform(Join(x4, x3), x5) # NB changed order here
        t5 = Transform(x5, End())

        g = GlobalType(x0, [t1, t2, t3, t4, t5 ])

        #breakpoint()
        g1 = g.simplify()

        self.assertEqual(g1.initial, x5)
        self.assertEqual(len(g1.transforms), 1)
        self.assertTrue(isinstance(g1.transforms[0].rhs, End))
        self.assertEqual(g1.transforms[0].lhs, x5)



    def test_simplify_join_fork_par_1_many_messages(self):

        x0 = StateVar("x0")
        x1 = StateVar("x1")
        x2 = StateVar("x2")
        x3 = StateVar("x3")
        x4 = StateVar("x4")
        x5 = StateVar("x5")
        x6 = StateVar("x6")

        m1 = MsgExc("Alice", "Bob", "Book", str)
        m2 = MsgExc("Alice", "Bob", "Film1", str)
        m3 = MsgExc("Alice", "Bob", "Film2", str)
        m4 = MsgExc("Alice", "Bob", "Film3", str)
        m5 = MsgExc("Alice", "Bob", "Film4", str)
        m6 = MsgExc("Alice", "Bob", "Film5", str)
        m7 = MsgExc("Alice", "Bob", "Film6", str)
        m8 = MsgExc("Alice", "Bob", "Film7", str)
        m9 = MsgExc("Alice", "Bob", "Film8", str)
        m10 = MsgExc("Alice", "Bob", "Film9", str)
        m11 = MsgExc("Alice", "Bob", "Film10", str)

        t1 = Transform(x0, Fork(x1, x2))
        t2 = Transform(x1, Concat(m1, m2, m3, m4, x3))
        t3 = Transform(x2, Concat(m5, m5, m7, m8, x4))
        t4 = Transform(Join(x3, x4), x5)
        t5 = Transform(x5, Concat(m9, m10, m11, x6))
        t6 = Transform(x6, End())

        g = GlobalType(x0, [t1, t2, t3, t4, t5, t6 ])

        #breakpoint()
        g1 = g.simplify()

        self.assertEqual(g1.initial, x6)
        self.assertEqual(len(g1.transforms), 1)
        self.assertTrue(isinstance(g1.transforms[0].rhs, End))
        self.assertEqual(g1.transforms[0].lhs, x6)


    def test_recursive_mpst_is_well_formed(self):

        x0 = StateVar("x0")
        x1 = StateVar("x1")
        x2 = StateVar("x2")

        m1 = MsgExc("Alice", "Bob", "Msg", str)

        t1 = Transform(Merge(x0, x2), x1)
        t2 = Transform(x1, Concat(m1, x2))

        g = GlobalType(x0, [t1, t2 ])

        g.set_debug(True)
        #breakpoint()
        g.check_wellformed()

       
## 
##    def test_cannot_simplify_join_fork_par_1(self):
##
##        x0 = StateVar("x0")
##        x1 = StateVar("x1")
##        x2 = StateVar("x2")
##        x3 = StateVar("x3")
##        x4 = StateVar("x4")
##        x5 = StateVar("x5")
##
##        m1 = MsgExc("Alice", "Bob", "Book", str)
##        m2 = MsgExc("Alice", "Bob", "Film", str)
##
##        t1 = Transform(x0, Fork(x1, x2))
##        t2 = Transform(x1, Concat(m1, x3))
##        t3 = Transform(x2, Concat(m2, x4))
##        t4 = Transform(Join(x3, x4), x5)
##        t5 = Transform(x5, End())
##
##        g = GlobalType(x0, [t1, t2, t3, t4, t5 ])
##
##        #breakpoint()
##        g1 = g.simplify()
##
##        self.assertEqual(g1.initial, x5)
##        self.assertEqual(len(g1.transforms), 1)
##        self.assertTrue(isinstance(g1.transforms[0].rhs, End))
##        self.assertEqual(g1.transforms[0].lhs, x5)
##
##
##               
