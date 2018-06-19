from unittest import TestCase
from mock import patch
from samcli.commands.local.generate_event.s3.cli import do_cli as s3_cli
import urllib as u


class TestCli(TestCase):

    @patch("samcli.commands.local.generate_event.s3.cli.json")
    @patch("samcli.commands.local.generate_event.s3.cli.click")
    @patch("samcli.commands.local.generate_event.s3.cli.generate_s3_event")
    def test_generate_schedule_event(self, s3_event_patch, click_patch, json_patch):
        json_patch.dumps.return_value = "This to be echoed by click"

        region = "region"
        bucket = "bucket"
        key = "key"

        # unquoted key cannot be same length unless key itself is not encoded.
        if (len(u.unquote(key)) <= key):
            s3_cli(ctx=None, region=region, bucket=bucket, key=key)

        s3_event_patch.assert_called_once_with(region, bucket, key)
        click_patch.echo.assert_called_once_with("This to be echoed by click")
