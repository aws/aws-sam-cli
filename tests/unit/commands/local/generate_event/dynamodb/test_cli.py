from unittest import TestCase
from mock import patch

from samcli.commands.local.generate_event.dynamodb.cli import do_cli as dynamodb_cli


class TestCli(TestCase):

    @patch("samcli.commands.local.generate_event.dynamodb.cli.json")
    @patch("samcli.commands.local.generate_event.dynamodb.cli.click")
    @patch("samcli.commands.local.generate_event.dynamodb.cli.generate_dynamodb_event")
    def test_generate_schedule_event(self, dynamodb_event_patch, click_patch, json_patch):
        json_patch.dumps.return_value = "This to be echoed by click"

        region = "region"

        dynamodb_cli(ctx=None, region=region)

        dynamodb_event_patch.assert_called_once_with(region)
        click_patch.echo.assert_called_once_with("This to be echoed by click")
