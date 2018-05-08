from unittest import TestCase
from mock import patch

from samcli.commands.local.generate_event.sns.cli import do_cli as sns_cli


class TestCli(TestCase):

    @patch("samcli.commands.local.generate_event.sns.cli.json")
    @patch("samcli.commands.local.generate_event.sns.cli.click")
    @patch("samcli.commands.local.generate_event.sns.cli.generate_sns_event")
    def test_generate_schedule_event(self, sns_event_patch, click_patch, json_patch):
        json_patch.dumps.return_value = "This to be echoed by click"

        message = "message"
        topic = "topic"
        subject = "subject"

        sns_cli(ctx=None, message=message, topic=topic, subject=subject)

        sns_event_patch.assert_called_once_with(message, topic, subject)
        click_patch.echo.assert_called_once_with("This to be echoed by click")
