import logging

from unittest import TestCase
from samcli.cli.context import Context


class TestContext(TestCase):

    def test_must_initialize_with_defaults(self):
        ctx = Context()

        self.assertEquals(ctx.debug, False, "debug must default to False")

    def test_must_set_get_debug_flag(self):
        ctx = Context()

        ctx.debug = True
        self.assertEquals(ctx.debug, True, "debug must be set to True")
        self.assertEquals(logging.getLogger().getEffectiveLevel(), logging.DEBUG)

    def test_must_unset_get_debug_flag(self):
        ctx = Context()

        ctx.debug = True
        self.assertEquals(ctx.debug, True, "debug must be set to True")

        # Flipping from True to False
        ctx.debug = False
        self.assertEquals(ctx.debug, False, "debug must be set to False")
