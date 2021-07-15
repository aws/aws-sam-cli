from unittest import TestCase
from unittest.mock import Mock, patch

from click import BadOptionUsage

from samcli.lib.cli_validation.payload_file_validation import payload_and_payload_file_options_validation


class TestPayloadFileValidation(TestCase):
    @patch("samcli.lib.cli_validation.payload_file_validation.click.get_current_context")
    def test_only_payload_param(self, patched_click_context):
        mock_func = Mock()

        mocked_context = Mock()
        patched_click_context.return_value = mocked_context

        mocked_context.params.get.side_effect = lambda key: "payload" if key == "payload" else None

        payload_and_payload_file_options_validation(mock_func)()

        mock_func.assert_called_once()

    @patch("samcli.lib.cli_validation.payload_file_validation.click.get_current_context")
    def test_only_payload_file_param(self, patched_click_context):
        mock_func = Mock()

        mocked_context = Mock()
        patched_click_context.return_value = mocked_context

        mocked_context.params.get.side_effect = lambda key: "payload_file" if key == "payload_file" else None

        payload_and_payload_file_options_validation(mock_func)()

        mock_func.assert_called_once()

    @patch("samcli.lib.cli_validation.payload_file_validation.click.get_current_context")
    def test_both_params(self, patched_click_context):
        mock_func = Mock()
        mocked_context = Mock()
        patched_click_context.return_value = mocked_context

        mocked_context.params.get.side_effect = lambda key: "payload_content"

        with self.assertRaises(BadOptionUsage) as ex:
            payload_and_payload_file_options_validation(mock_func)()

        self.assertIn("Both '--payload-file' and '--payload' cannot be provided.", ex.exception.message)

        mock_func.assert_not_called()
