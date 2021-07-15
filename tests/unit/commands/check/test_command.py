from unittest import TestCase
from unittest.mock import Mock, patch

from samcli.commands.check.command import do_cli


class TestCheckCli(TestCase):
    def test_do_cli(self):
        with patch("samcli.commands.check.lib.command_context.CheckContext") as patched_context:
            ctx = Mock()
            ctx.region.return_value = Mock()
            ctx.profile.return_value = Mock()

            template_path = Mock()

            check_context = Mock()

            patched_context.return_value = check_context

            check_context.run = Mock()

            do_cli(ctx, template_path)

            patched_context.assert_called_once_with(ctx.region, ctx.profile, template_path)
            check_context.run.assert_called_once()
