from unittest import TestCase
from unittest.mock import Mock, patch

from samcli.commands.check.command import do_cli


class TestCheckCli(TestCase):
    @patch("samcli.commands.check.command.CheckContext")
    def test_do_cli(self, patched_context):
        ctx = Mock()
        template_path = Mock()

        check_context = Mock()

        patched_context.return_value = check_context

        check_context.run = Mock()

        do_cli(ctx, template_path)

        patched_context.assert_called_once_with(ctx, template_path)
        check_context.run.assert_called_once()
