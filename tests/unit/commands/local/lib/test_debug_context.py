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
