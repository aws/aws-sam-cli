from unittest import TestCase
from unittest.mock import Mock, patch

from click import BadOptionUsage

from samcli.lib.cli_validation.remote_invoke_options_validations import (
    event_and_event_file_options_validation,
    stack_name_or_resource_id_atleast_one_option_validation,
)


class TestEventFileValidation(TestCase):
    @patch("samcli.lib.cli_validation.remote_invoke_options_validations.LOG")
    @patch("samcli.lib.cli_validation.remote_invoke_options_validations.click.get_current_context")
    def test_both_not_provided_params(self, patched_click_context, patched_log):
        mock_func = Mock()
        mocked_context = Mock()
        patched_click_context.return_value = mocked_context

        mocked_context.params.get.return_value = {}

        event_and_event_file_options_validation(mock_func)()
        patched_log.debug.assert_called_with(
            "Neither --event nor --event-file options have been provided, reading from stdin"
        )

        mock_func.assert_called_once()

    @patch("samcli.lib.cli_validation.remote_invoke_options_validations.click.get_current_context")
    def test_only_event_param(self, patched_click_context):
        mock_func = Mock()

        mocked_context = Mock()
        patched_click_context.return_value = mocked_context

        mocked_context.params.get.side_effect = lambda key: "event" if key == "event" else None

        event_and_event_file_options_validation(mock_func)()

        mock_func.assert_called_once()

    @patch("samcli.lib.cli_validation.remote_invoke_options_validations.click.get_current_context")
    def test_only_event_file_param(self, patched_click_context):
        mock_func = Mock()

        mocked_context = Mock()
        patched_click_context.return_value = mocked_context

        mocked_context.params.get.side_effect = lambda key: "event_file" if key == "event_file" else None

        event_and_event_file_options_validation(mock_func)()

        mock_func.assert_called_once()

    @patch("samcli.lib.cli_validation.remote_invoke_options_validations.click.get_current_context")
    def test_both_params(self, patched_click_context):
        mock_func = Mock()
        mocked_context = Mock()
        patched_click_context.return_value = mocked_context

        mocked_context.params.get.side_effect = lambda key: "event_content"

        with self.assertRaises(BadOptionUsage) as ex:
            event_and_event_file_options_validation(mock_func)()

        self.assertIn("Both '--event-file' and '--event' cannot be provided.", ex.exception.message)

        mock_func.assert_not_called()


class TestRemoteInvokeAtleast1OptionProvidedValidation(TestCase):
    @patch("samcli.lib.cli_validation.remote_invoke_options_validations.click.get_current_context")
    def test_only_resource_id_param(self, patched_click_context):
        mock_func = Mock()

        mocked_context = Mock()
        patched_click_context.return_value = mocked_context

        mocked_context.params.get.side_effect = lambda key: "resource_id" if key == "resource_id" else None

        stack_name_or_resource_id_atleast_one_option_validation(mock_func)()

        mock_func.assert_called_once()

    @patch("samcli.lib.cli_validation.remote_invoke_options_validations.click.get_current_context")
    def test_only_stack_name_param(self, patched_click_context):
        mock_func = Mock()

        mocked_context = Mock()
        patched_click_context.return_value = mocked_context

        mocked_context.params.get.side_effect = lambda key: "stack_name" if key == "stack_name" else None

        stack_name_or_resource_id_atleast_one_option_validation(mock_func)()

        mock_func.assert_called_once()

    @patch("samcli.lib.cli_validation.remote_invoke_options_validations.click.get_current_context")
    def test_no_params_provided(self, patched_click_context):
        mock_func = Mock()
        mocked_context = Mock()
        patched_click_context.return_value = mocked_context

        mocked_context.params.get.return_value = {}

        with self.assertRaises(BadOptionUsage) as ex:
            stack_name_or_resource_id_atleast_one_option_validation(mock_func)()

        self.assertIn("Atleast 1 of --stack-name or --resource-id parameters should be provided.", ex.exception.message)

        mock_func.assert_not_called()
