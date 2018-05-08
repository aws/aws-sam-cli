from unittest import TestCase
from mock import patch

from samcli.commands.local.generate_event.kinesis.cli import do_cli as kinesis_cli


class TestCli(TestCase):

    @patch("samcli.commands.local.generate_event.kinesis.cli.json")
    @patch("samcli.commands.local.generate_event.kinesis.cli.click")
    @patch("samcli.commands.local.generate_event.kinesis.cli.generate_kinesis_event")
    def test_generate_schedule_event(self, kinesis_event_patch, click_patch, json_patch):
        json_patch.dumps.return_value = "This to be echoed by click"

        region = "region"
        partition = "partition"
        sequence = "sequence"
        data = "data"

        data_base64 = b"ZGF0YQ=="

        kinesis_cli(ctx=None, region=region, partition=partition, sequence=sequence, data=data)

        kinesis_event_patch.assert_called_once_with(region, partition, sequence, data_base64)
        click_patch.echo.assert_called_once_with("This to be echoed by click")
