"""
Unit tests for DurableCallbackHandler
"""

import threading
from unittest import TestCase
from unittest.mock import Mock, patch

from parameterized import parameterized

from samcli.lib.utils.durable_callback_handler import (
    DurableCallbackHandler,
    CHOICE_SUCCESS,
    CHOICE_FAILURE,
    CHOICE_HEARTBEAT,
    CHOICE_STOP,
)


class TestDurableCallbackHandler(TestCase):
    def setUp(self):
        self.mock_client = Mock()
        self.handler = DurableCallbackHandler(self.mock_client)

    def test_init(self):
        """Test handler initializes with client and empty prompted callbacks set"""
        self.assertEqual(self.handler.client, self.mock_client)
        self.assertEqual(self.handler._prompted_callbacks, set())

    @parameterized.expand(
        [
            (
                "with_pending_callback",
                {
                    "Events": [
                        {
                            "Id": 1,
                            "EventType": "CallbackStarted",
                            "CallbackStartedDetails": {"CallbackId": "callback-123"},
                        },
                        {"Id": 2, "EventType": "StepStarted"},
                    ]
                },
                "callback-123",
            ),
            (
                "with_completed_callback",
                {
                    "Events": [
                        {
                            "Id": 1,
                            "EventType": "CallbackStarted",
                            "CallbackStartedDetails": {"CallbackId": "callback-123"},
                        },
                        {"Id": 1, "EventType": "CallbackCompleted"},
                    ]
                },
                None,
            ),
            (
                "no_callbacks",
                {"Events": [{"Id": 1, "EventType": "StepStarted"}]},
                None,
            ),
        ]
    )
    def test_check_for_pending_callbacks(self, name, history_response, expected_callback_id):
        """Test checking for pending callbacks"""
        self.mock_client.get_durable_execution_history.return_value = history_response

        callback_id = self.handler.check_for_pending_callbacks("test-arn")

        self.assertEqual(callback_id, expected_callback_id)
        self.mock_client.get_durable_execution_history.assert_called_once_with("test-arn")

    def test_check_for_pending_callbacks_handles_exception(self):
        """Test that exceptions during callback check are handled gracefully"""
        self.mock_client.get_durable_execution_history.side_effect = Exception("API error")

        callback_id = self.handler.check_for_pending_callbacks("test-arn")

        self.assertIsNone(callback_id)

    @parameterized.expand(
        [
            (
                "success",
                CHOICE_SUCCESS,
                ["test result"],
                "send_callback_success",
                {"callback_id": "callback-123", "result": "test result"},
                True,
            ),
            (
                "failure",
                CHOICE_FAILURE,
                ["Error occurred", "CustomError"],
                "send_callback_failure",
                {"callback_id": "callback-123", "error_message": "Error occurred", "error_type": "CustomError"},
                True,
            ),
            (
                "heartbeat",
                CHOICE_HEARTBEAT,
                [],
                "send_callback_heartbeat",
                {"callback_id": "callback-123"},
                False,
            ),
            (
                "stop_execution",
                CHOICE_STOP,
                ["Execution stopped by user", "StopError"],
                "stop_durable_execution",
                {
                    "durable_execution_arn": "test-arn",
                    "error_message": "Execution stopped by user",
                    "error_type": "StopError",
                },
                True,
            ),
        ]
    )
    @patch("samcli.lib.utils.durable_callback_handler.click.prompt")
    @patch("samcli.lib.utils.durable_callback_handler.click.echo")
    def test_prompt_callback_response(
        self,
        name,
        choice,
        prompt_responses,
        method_name,
        expected_call_args,
        expected_result,
        mock_echo,
        mock_prompt,
    ):
        """Test prompting for different callback response types"""
        mock_prompt.side_effect = [choice] + prompt_responses

        result = self.handler.prompt_callback_response("test-arn", "callback-123")

        self.assertEqual(result, expected_result)
        lambda_client_api_call = getattr(self.mock_client, method_name)
        lambda_client_api_call.assert_called_once_with(**expected_call_args)
        self.assertIn("callback-123", self.handler._prompted_callbacks)

    def test_prompt_callback_response_only_prompts_once(self):
        """Test that callback is only prompted once per ID"""
        self.handler._prompted_callbacks.add("callback-123")

        result = self.handler.prompt_callback_response("test-arn", "callback-123")

        self.assertFalse(result)
        self.mock_client.send_callback_success.assert_not_called()

    @parameterized.expand(
        [
            ("before_prompt", True, False),
            ("after_selection", False, True),
        ]
    )
    @patch("samcli.lib.utils.durable_callback_handler.click.prompt")
    @patch("samcli.lib.utils.durable_callback_handler.click.echo")
    def test_prompt_callback_response_checks_execution_complete(
        self, name, set_before_prompt, set_during_prompt, mock_echo, mock_prompt
    ):
        """Test that prompt respects execution_complete event"""
        execution_complete = threading.Event()

        if set_before_prompt:
            execution_complete.set()
        elif set_during_prompt:

            def prompt_side_effect(*args, **kwargs):
                execution_complete.set()
                return CHOICE_SUCCESS

            mock_prompt.side_effect = prompt_side_effect

        result = self.handler.prompt_callback_response("test-arn", "callback-123", execution_complete)

        self.assertFalse(result)
        self.mock_client.send_callback_success.assert_not_called()
        if set_before_prompt:
            mock_prompt.assert_not_called()

    @patch("samcli.lib.utils.durable_callback_handler.click.prompt")
    @patch("samcli.lib.utils.durable_callback_handler.click.echo")
    def test_prompt_callback_response_handles_exception(self, mock_echo, mock_prompt):
        """Test that exceptions during callback send are handled gracefully"""
        mock_prompt.return_value = CHOICE_HEARTBEAT

        self.mock_client.send_callback_heartbeat.side_effect = Exception("API error")

        result = self.handler.prompt_callback_response("test-arn", "callback-123")

        self.assertFalse(result)
