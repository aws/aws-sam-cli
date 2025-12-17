from unittest import TestCase

from parameterized import parameterized

from samcli.commands.local.lib.debug_context import DebugContext


class TestDebugContext(TestCase):
    def test_init(self):
        context = DebugContext("port", "debuggerpath", "debug_args")

        self.assertEqual(context.debug_ports, "port")
        self.assertEqual(context.debugger_path, "debuggerpath")
        self.assertEqual(context.debug_args, "debug_args")

    @parameterized.expand(
        [
            ("1000", "debuggerpath", "debug_args"),
            (["1000"], "debuggerpath", "debug_args"),
            (["1000", "1001"], "debuggerpath", "debug_args"),
            (1000, "debuggerpath", "debug_args"),
            ([1000], "debuggerpath", "debug_args"),
            ([1000, 1001], "debuggerpath", "debug_args"),
            ([1000], None, None),
            ([1000], None, "debug_args"),
            ([1000], "debuggerpath", None),
        ]
    )
    def test_bool_truthy(self, port, debug_path, debug_ars):
        debug_context = DebugContext(port, debug_path, debug_ars)

        self.assertTrue(debug_context.__bool__())

    @parameterized.expand(
        [
            (None, "debuggerpath", "debug_args"),
            (None, None, None),
            (None, None, "debug_args"),
            (None, "debuggerpath", None),
        ]
    )
    def test_bool_falsy(self, port, debug_path, debug_ars):
        debug_context = DebugContext(port, debug_path, debug_ars)

        self.assertFalse(debug_context.__bool__())

    @parameterized.expand(
        [
            ("1000", "debuggerpath", "debug_args"),
            (["1000"], "debuggerpath", "debug_args"),
            (["1000", "1001"], "debuggerpath", "debug_args"),
            (1000, "debuggerpath", "debug_args"),
            ([1000], "debuggerpath", "debug_args"),
            ([1000, 1001], "debuggerpath", "debug_args"),
            ([1000], None, None),
            ([1000], None, "debug_args"),
            ([1000], "debuggerpath", None),
        ]
    )
    def test_nonzero_thruthy(self, port, debug_path, debug_ars):
        debug_context = DebugContext(port, debug_path, debug_ars)

        self.assertTrue(debug_context.__nonzero__())

    @parameterized.expand(
        [
            (None, "debuggerpath", "debug_args"),
            (None, None, None),
            (None, None, "debug_args"),
            (None, "debuggerpath", None),
        ]
    )
    def test_nonzero_falsy(self, port, debug_path, debug_ars):
        debug_context = DebugContext(port, debug_path, debug_ars)

        self.assertFalse(debug_context.__nonzero__())

    def test_equality_same_contexts(self):
        """Test that identical debug contexts are equal"""
        context1 = DebugContext(
            debug_ports=(5858,),
            debugger_path="/usr/bin/debugger",
            debug_args="--wait",
            debug_function="MyFunction",
            container_env_vars={"VAR1": "value1"},
        )
        context2 = DebugContext(
            debug_ports=(5858,),
            debugger_path="/usr/bin/debugger",
            debug_args="--wait",
            debug_function="MyFunction",
            container_env_vars={"VAR1": "value1"},
        )

        self.assertEqual(context1, context2)
        self.assertEqual(hash(context1), hash(context2))

    def test_equality_different_contexts(self):
        """Test that different debug contexts are not equal"""
        context1 = DebugContext(debug_ports=(5858,), debug_function="MyFunction")
        context2 = DebugContext(debug_ports=(9229,), debug_function="MyFunction")  # Different port
        context3 = DebugContext(debug_ports=(5858,), debug_function="OtherFunction")  # Different function

        self.assertNotEqual(context1, context2)
        self.assertNotEqual(context1, context3)
        self.assertNotEqual(context2, context3)

    def test_equality_with_none(self):
        """Test that debug context is not equal to None or other types"""
        context = DebugContext(debug_ports=(5858,))

        self.assertNotEqual(context, None)
        self.assertNotEqual(context, "string")
        self.assertNotEqual(context, 123)
        self.assertNotEqual(context, {})

    def test_equality_none_values(self):
        """Test equality with None values in attributes"""
        context1 = DebugContext(debug_ports=None, debug_function=None)
        context2 = DebugContext(debug_ports=None, debug_function=None)
        context3 = DebugContext(debug_ports=(5858,), debug_function=None)

        self.assertEqual(context1, context2)
        self.assertNotEqual(context1, context3)
