from unittest import TestCase
from unittest.mock import Mock, patch

from click import BadOptionUsage

from samcli.lib.cli_validation.event_file_validation import event_and_event_file_options_validation


class TestEventFileValidation(TestCase):
    @patch("samcli.lib.cli_validation.event_file_validation.click.get_current_context")
    def test_only_event_param(self, patched_click_context):
        mock_func = Mock()

        mocked_context = Mock()
        patched_click_context.return_value = mocked_context

        mocked_context.params.get.side_effect = lambda key: "event" if key == "event" else None

        event_and_event_file_options_validation(mock_func)()

        mock_func.assert_called_once()

    @patch("samcli.lib.cli_validation.event_file_validation.click.get_current_context")
    def test_only_event_file_param(self, patched_click_context):
        mock_func = Mock()

        mocked_context = Mock()
        patched_click_context.return_value = mocked_context

        mocked_context.params.get.side_effect = lambda key: "event_file" if key == "event_file" else None

        event_and_event_file_options_validation(mock_func)()

        mock_func.assert_called_once()

    @patch("samcli.lib.cli_validation.event_file_validation.click.get_current_context")
    def test_both_params(self, patched_click_context):
        mock_func = Mock()
        mocked_context = Mock()
        patched_click_context.return_value = mocked_context

        mocked_context.params.get.side_effect = lambda key: "event_content"

        with self.assertRaises(BadOptionUsage) as ex:
            event_and_event_file_options_validation(mock_func)()

        self.assertIn("Both '--event-file' and '--event' cannot be provided.", ex.exception.message)

        mock_func.assert_not_called()
