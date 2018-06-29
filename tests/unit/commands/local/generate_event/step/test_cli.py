from unittest import TestCase
from mock import patch

from samcli.commands.local.generate_event.step.cli import do_cli as step_cli


class TestCli(TestCase):

    @patch("samcli.commands.local.generate_event.step.cli.json")
    @patch("samcli.commands.local.generate_event.step.cli.click")
    @patch("samcli.commands.local.generate_event.step.cli.generate_step_event")
    def test_generate_step_event(self, step_event_patch, click_patch, json_patch):
        json_patch.dumps.return_value = "This to be echoed by click"

        key = "key"
        value = "value"
        filepath = ""

        step_cli(ctx=None, key=key, value=value, filepath=filepath)

        step_event_patch.assert_called_once_with(key, value)
        click_patch.echo.assert_called_once_with("This to be echoed by click")
