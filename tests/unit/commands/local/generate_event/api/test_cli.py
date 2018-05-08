from unittest import TestCase
from mock import patch

from samcli.commands.local.generate_event.api.cli import do_cli as api_cli


class TestCli(TestCase):

    @patch("samcli.commands.local.generate_event.api.cli.json")
    @patch("samcli.commands.local.generate_event.api.cli.click")
    @patch("samcli.commands.local.generate_event.api.cli.generate_api_event")
    def test_generate_schedule_event(self, api_event_patch, click_patch, json_patch):
        json_patch.dumps.return_value = "This to be echoed by click"

        method = "method"
        body = "body"
        resource = "resource"
        path = "path"

        api_cli(ctx=None, method=method, body=body, resource=resource, path=path)

        api_event_patch.assert_called_once_with(method, body, resource, path)
        click_patch.echo.assert_called_once_with("This to be echoed by click")
