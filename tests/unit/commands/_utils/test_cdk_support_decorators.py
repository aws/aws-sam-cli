from unittest import TestCase
from unittest.mock import patch, Mock, call

from samcli.commands._utils.cdk_support_decorators import unsupported_command_cdk


class TestUnsupportedCDKCommand(TestCase):
    @patch("samcli.commands._utils.cdk_support_decorators.Context")
    @patch("samcli.commands._utils.cdk_support_decorators.is_cdk_project")
    @patch("click.secho")
    def test_must_emit_warning_message_no_suggestion(self, secho_mock, is_cdk_project_mock, context_mock):
        is_cdk_project_mock.return_value = True

        def real_fn():
            return True

        unsupported_command_cdk(None)(real_fn)()

        secho_mock.assert_called_with("Warning: CDK apps are not officially supported with this command.", fg="yellow")

    @patch("samcli.commands._utils.cdk_support_decorators.Context")
    @patch("samcli.commands._utils.cdk_support_decorators.is_cdk_project")
    @patch("click.secho")
    def test_must_emit_warning_message_with_suggestion(self, secho_mock, is_cdk_project_mock, context_mock):
        is_cdk_project_mock.return_value = True

        def real_fn():
            return True

        unsupported_command_cdk("Alternate command")(real_fn)()
        expected_calls = [
            call("Warning: CDK apps are not officially supported with this command.", fg="yellow"),
            call("We recommend you use this alternative command: Alternate command", fg="yellow"),
        ]

        secho_mock.assert_has_calls(expected_calls)

    @patch("samcli.commands._utils.cdk_support_decorators.Context")
    @patch("samcli.commands._utils.cdk_support_decorators.is_cdk_project")
    @patch("click.secho")
    def test_must_not_emit_warning_message(self, secho_mock, is_cdk_project_mock, context_mock):
        is_cdk_project_mock.return_value = False

        def real_fn():
            return True

        unsupported_command_cdk(None)(real_fn)()

        secho_mock.assert_not_called()
