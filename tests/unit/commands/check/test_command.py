from unittest import TestCase
from unittest.mock import Mock, patch

from samcli.commands.check.command import do_cli


class TestCheckCli(TestCase):
    @patch("samcli.commands.check.lib.command_context.CheckContext")
    def test_do_cli(self, patched_context):
        # Test not constructed properly. Looking into
        ctx = Mock()
        template_path = Mock()

        result = do_cli(ctx, template_path)

        patched_context.assert_called_with(ctx, template_path)


# def do_cli(ctx, template_path):
#     """
#     Implementation of the ``cli`` method
#     """

#     context = CheckContext(ctx, template_path)
#     context.run()
