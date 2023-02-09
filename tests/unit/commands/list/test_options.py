from unittest import TestCase
from unittest.mock import patch

from samcli.commands.list.cli_common.options import stack_name_not_provided_message, STACK_NAME_WARNING_MESSAGE


class TestCommonOptions(TestCase):
    @patch("samcli.commands.list.cli_common.options.click")
    def test_echoes_warning_messages(self, mock_click):
        stack_name_not_provided_message()
        mock_click.secho.assert_called_once_with(
            fg="yellow",
            message=STACK_NAME_WARNING_MESSAGE,
            err=True,
        )
