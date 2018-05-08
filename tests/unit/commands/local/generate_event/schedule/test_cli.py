from unittest import TestCase
from mock import patch

from samcli.commands.local.generate_event.schedule.cli import do_cli as schedule_cli


class TestCli(TestCase):

    @patch("samcli.commands.local.generate_event.schedule.cli.json")
    @patch("samcli.commands.local.generate_event.schedule.cli.click")
    @patch("samcli.commands.local.generate_event.schedule.cli.generate_schedule_event")
    def test_generate_schedule_event(self, schedule_event_patch, click_patch, json_patch):
        json_patch.dumps.return_value = "This to be echoed by click"

        region = "us-east-1"

        schedule_cli(ctx=None, region=region)

        schedule_event_patch.assert_called_once_with(region)
        click_patch.echo.assert_called_once_with("This to be echoed by click")
