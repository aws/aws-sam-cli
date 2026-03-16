"""
Unit tests for shared formatting utilities
"""

from unittest import TestCase
from datetime import datetime, timezone
import pytest
from parameterized import parameterized

from samcli.lib.utils.durable_formatters import (
    format_timestamp,
    format_execution_history,
    format_execution_details,
    format_event_details,
    format_execution_history_table,
    format_execution_details_summary,
    format_next_commands_after_invoke,
    format_callback_success_message,
    format_callback_failure_message,
    format_callback_heartbeat_message,
    format_stop_execution_message,
    format_event_result,
)


class TestFormatTimestamp(TestCase):
    """Test cases for format_timestamp function"""

    @parameterized.expand(
        [
            (datetime(2023, 1, 1, 12, 30, 45), "12:30:45"),
            (None, "-"),
            ("invalid", "invalid"),
        ]
    )
    def test_format_timestamp(self, timestamp, expected):
        """Test format_timestamp with various inputs"""
        result = format_timestamp(timestamp)
        self.assertEqual(result, expected)


class TestFormatExecutionHistory(TestCase):
    """Test cases for format_execution_history function"""

    def test_format_execution_history_json(self):
        """Test JSON format output"""
        history_result = {"Events": [{"EventId": 1}], "ResponseMetadata": {"RequestId": "123"}}
        result = format_execution_history(history_result, "json")
        self.assertIn('"Events"', result)
        self.assertNotIn('"ResponseMetadata"', result)

    def test_format_execution_history_table_default(self):
        """Test table format (default) output"""
        history_result = {"Events": []}
        result = format_execution_history(history_result)
        self.assertEqual(result, "No execution events found.")

    def test_format_execution_history_table_with_events(self):
        """Test table format with events - tests _create_table internally"""
        history_result = {
            "Events": [
                {
                    "EventId": 1,
                    "EventType": "ExecutionStarted",
                    "Name": "MyExecution",
                    "SubType": "Standard",
                    "EventTimestamp": datetime(2023, 1, 1, 12, 0, 0),
                }
            ]
        }
        result = format_execution_history(history_result, "table")
        # Verify table structure is created
        self.assertIn("│", result)
        self.assertIn("┌", result)
        self.assertIn("ExecutionStarted", result)
        self.assertIn("MyExecution", result)


class TestFormatExecutionDetails(TestCase):
    """Test cases for format_execution_summary function"""

    def test_format_execution_summary_json(self):
        """Test JSON format output"""
        execution_arn = "test-arn"
        execution_details = {"Status": "SUCCEEDED", "ResponseMetadata": {"RequestId": "123"}}
        result = format_execution_details(execution_arn, execution_details, "json")
        self.assertIn('"Status"', result)
        self.assertNotIn('"ResponseMetadata"', result)

    def test_format_execution_summary_text_default(self):
        """Test summary format (default) output"""
        execution_arn = "test-arn"
        execution_details = {"Status": "SUCCEEDED"}
        result = format_execution_details(execution_arn, execution_details)
        self.assertIn("Execution Summary:", result)


class TestFormatExecutionHistoryTable(TestCase):
    """Test cases for format_execution_history_table function"""

    @parameterized.expand(
        [
            ({"EventType": "ExecutionStarted", "ExecutionStartedDetails": {"ExecutionTimeout": 300}}, "Timeout: 300s"),
            ({"EventType": "ExecutionStarted", "ExecutionStartedDetails": {}}, ""),
            ({"EventType": "WaitStarted", "WaitStartedDetails": {"Duration": 59}}, "Duration: 59s"),
            ({"EventType": "WaitStarted", "WaitStartedDetails": {}}, ""),
            (
                {"EventType": "CallbackStarted", "CallbackStartedDetails": {"Timeout": 5, "HeartbeatTimeout": 2}},
                "Timeout: 5s, Heartbeat: 2s",
            ),
            ({"EventType": "CallbackStarted", "CallbackStartedDetails": {"Timeout": 5}}, "Timeout: 5s"),
            ({"EventType": "CallbackStarted", "CallbackStartedDetails": {"HeartbeatTimeout": 2}}, "Heartbeat: 2s"),
            ({"EventType": "CallbackStarted", "CallbackStartedDetails": {}}, ""),
            (
                {"EventType": "StepSucceeded", "StepSucceededDetails": {"RetryDetails": {"CurrentAttempt": 3}}},
                "Retries Attempted: 2",
            ),
            ({"EventType": "StepSucceeded", "StepSucceededDetails": {"RetryDetails": {"CurrentAttempt": 1}}}, ""),
            ({"EventType": "StepSucceeded", "StepSucceededDetails": {}}, ""),
            ({"EventType": "StepSucceeded", "StepSucceededDetails": {"RetryDetails": {}}}, ""),
            (
                {"EventType": "InvocationCompleted", "InvocationCompletedDetails": {"RequestId": "abc-123"}},
                "Invocation Id: abc-123",
            ),
            ({"EventType": "InvocationCompleted", "InvocationCompletedDetails": {}}, ""),
            (
                {"EventType": "ExecutionTimedOut", "ExecutionTimedOutDetails": {"Error": "Timeout exceeded"}},
                "Error: Timeout exceeded",
            ),
            ({"EventType": "ExecutionTimedOut", "ExecutionTimedOutDetails": {}}, "Execution exceeded timeout"),
            ({"EventType": "UnknownEvent"}, ""),
        ]
    )
    def test_format_event_details(self, event, expected):
        """Test format_event_details with various event types"""
        result = format_event_details(event)
        self.assertEqual(result, expected)

    @parameterized.expand(
        [
            (
                {"EventType": "ExecutionStarted", "ExecutionStartedDetails": {"Input": {"Payload": "input data"}}},
                "input data",
            ),
            ({"EventType": "ExecutionStarted", "ExecutionStartedDetails": {"Input": "direct input"}}, "direct input"),
            (
                {"EventType": "StepSucceeded", "StepSucceededDetails": {"Result": {"Payload": "output data"}}},
                "output data",
            ),
            ({"EventType": "StepSucceeded", "StepSucceededDetails": {"Result": {"Truncated": False}}}, "-"),
            (
                {
                    "EventType": "InvocationCompleted",
                    "InvocationCompletedDetails": {"Result": {"Payload": "result data"}},
                },
                "result data",
            ),
            (
                {
                    "EventType": "ExecutionSucceeded",
                    "ExecutionSucceededDetails": {"Result": {"Payload": "final result"}},
                },
                "final result",
            ),
            (
                {
                    "EventType": "CallbackSucceeded",
                    "CallbackSucceededDetails": {"Result": {"Payload": "callback result"}},
                },
                "callback result",
            ),
            (
                {
                    "EventType": "ChainedInvokeSucceeded",
                    "ChainedInvokeSucceededDetails": {"Result": {"Payload": "chained result"}},
                },
                "chained result",
            ),
            (
                {"EventType": "ContextSucceeded", "ContextSucceededDetails": {"Result": {"Payload": "context result"}}},
                "context result",
            ),
            ({"EventType": "UnknownEvent"}, "-"),
            ({"EventType": "ExecutionStarted", "ExecutionStartedDetails": {}}, "-"),
            (
                {"EventType": "ExecutionStarted", "ExecutionStartedDetails": {"Input": {"Payload": "x" * 101}}},
                "x" * 97 + "...",
            ),
            (
                {"EventType": "StepSucceeded", "StepSucceededDetails": {"Result": "x" * 101}},
                "x" * 97 + "...",
            ),
            (
                {"EventType": "ExecutionStarted", "ExecutionStartedDetails": {"Input": {"Payload": "x" * 100}}},
                "x" * 100,
            ),
        ]
    )
    def test_format_event_result(self, event, expected):
        """Test format_event_result with various event types and payloads"""
        result, _ = format_event_result(event)
        self.assertEqual(result, expected)

    def test_format_table_with_events(self):
        """Test formatting table with events"""
        history_data = {
            "Events": [
                {
                    "EventId": 1,
                    "EventType": "ExecutionStarted",
                    "Name": "MyExecution",
                    "SubType": "Standard",
                    "EventTimestamp": datetime(2023, 1, 1, 12, 0, 0),
                }
            ]
        }
        result = format_execution_history_table(history_data, "test-arn")
        self.assertIn("│", result)
        self.assertIn("┌", result)
        self.assertIn("ExecutionStarted", result)
        self.assertIn("MyExecution", result)

    def test_format_table_no_events(self):
        """Test formatting table with no events"""
        history_data = {"Events": []}
        result = format_execution_history_table(history_data, "test-arn")
        self.assertEqual(result, "No execution events found.")

    def test_format_table_missing_events_key(self):
        """Test formatting table with missing Events key"""
        history_data = {}
        result = format_execution_history_table(history_data, "test-arn")
        self.assertEqual(result, "No execution events found.")

    @parameterized.expand(
        [
            (
                {
                    "EventType": "ExecutionFailed",
                    "ExecutionFailedDetails": {
                        "Error": {"Payload": {"ErrorType": "ValueError", "ErrorMessage": "Invalid input"}}
                    },
                },
                "ValueError: Invalid input",
            ),
            (
                {
                    "EventType": "StepFailed",
                    "StepFailedDetails": {"Error": {"Payload": {"ErrorType": "TimeoutError", "ErrorMessage": ""}}},
                },
                "TimeoutError",
            ),
            (
                {
                    "EventType": "StepFailed",
                    "StepFailedDetails": {"Error": {"Payload": {"ErrorType": "", "ErrorMessage": "Something failed"}}},
                },
                "Something failed",
            ),
            (
                {
                    "EventType": "ExecutionFailed",
                    "ExecutionFailedDetails": {
                        "Error": {"Payload": {"ErrorType": "LongError", "ErrorMessage": "x" * 100}}
                    },
                },
                "LongError: xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx...",
            ),
            (
                {
                    "EventType": "StepFailed",
                    "StepFailedDetails": {"Error": {"Payload": {"ErrorType": "x" * 101, "ErrorMessage": ""}}},
                },
                "x" * 57 + "...",
            ),
            (
                {
                    "EventType": "ExecutionFailed",
                    "ExecutionFailedDetails": {"Error": {"Payload": {"ErrorType": "Error", "ErrorMessage": "x" * 90}}},
                },
                f"Error: {'x' * 50}...",
            ),
        ]
    )
    def test_format_event_error(self, event, expected):
        """Test error extraction and formatting in table with various error events"""
        history_data = {
            "Events": [
                {
                    "EventId": 1,
                    "Name": "MyExecution",
                    "SubType": "Standard",
                    "EventTimestamp": datetime(2023, 1, 1, 12, 0, 0),
                    **event,
                }
            ]
        }
        result = format_execution_history_table(history_data, "test-arn")
        self.assertIn(expected, result)


class TestFormatExecutionDetailsSummary(TestCase):
    """Test cases for format_execution_summary_text function"""

    def test_format_execution_details_summary(self):
        """Test format_execution_summary_text returns expected structure"""
        execution_arn = "arn:aws:lambda:us-east-1:123456789012:function:MyFunction:$LATEST/durable-execution/my-execution-name/my-execution-id"
        execution_details = {
            "DurableExecutionName": "my-execution",
            "Status": "SUCCEEDED",
            "Result": '"Hello World!"',
            "StartTimestamp": datetime(2025, 11, 18, 12, 24, 56, tzinfo=timezone.utc),
            "EndTimestamp": datetime(2025, 11, 18, 12, 24, 57, 508000, tzinfo=timezone.utc),
        }

        result = format_execution_details_summary(execution_arn, execution_details)

        self.assertIn("Execution Summary:", result)
        self.assertIn("SUCCEEDED ✅", result)
        self.assertIn("ARN:", result)
        self.assertIn("Duration: 1.51s", result)
        self.assertIn("Name:", result)
        self.assertIn("Status:", result)
        self.assertIn("Result:", result)

    def test_format_execution_details_summary_no_timestamps(self):
        """Test format with no start/end timestamps"""
        execution_arn = "test-arn"
        execution_details = {"Status": "RUNNING"}
        result = format_execution_details_summary(execution_arn, execution_details)
        self.assertIn("Duration: N/A", result)

    def test_format_execution_details_summary_with_error(self):
        """Test format with failed execution showing error details"""
        execution_arn = "test-arn"
        execution_details = {
            "DurableExecutionName": "failed-execution",
            "Status": "FAILED",
            "InputPayload": '{"test": "data"}',
            "StartTimestamp": datetime(2025, 11, 21, 20, 18, 47, tzinfo=timezone.utc),
            "Error": {"ErrorType": "StepError", "ErrorMessage": "Your API Key Expired!"},
        }
        result = format_execution_details_summary(execution_arn, execution_details)

        self.assertIn("FAILED ❌", result)
        self.assertIn("Duration: N/A", result)
        self.assertIn("Error:    StepError: Your API Key Expired!", result)
        self.assertNotIn("Result:", result)

    @parameterized.expand(
        [
            ("RUNNING", "RUNNING"),
            ("FAILED", "FAILED ❌"),
            ("TIMED_OUT", "TIMED_OUT ⚠️"),
            ("STOPPED", "STOPPED ⚠️"),
        ]
    )
    def test_format_execution_details_summary_status_display(self, status, expected_display):
        """Test format with different status values"""
        execution_arn = "test-arn"
        execution_details = {"Status": status}
        result = format_execution_details_summary(execution_arn, execution_details)
        self.assertIn(expected_display, result)


class TestFormatNextCommandsAfterInvoke(TestCase):
    """Test cases for format_next_commands_after_invoke function"""

    def test_format_next_commands_after_invoke(self):
        """Test format_next_commands_after_invoke returns expected commands"""
        execution_arn = "test-arn"
        result = format_next_commands_after_invoke(execution_arn)

        self.assertIn("Commands you can use next", result)
        self.assertIn("Get execution details", result)
        self.assertIn("View execution history", result)
        self.assertIn(f"sam local execution get {execution_arn}", result)
        self.assertIn(f"sam local execution history {execution_arn}", result)


class TestFormatCallbackMessages(TestCase):
    """Test cases for callback message formatting functions"""

    @parameterized.expand(
        [
            ("test-id-123", "success result", "✅ Callback success sent for ID: test-id-123\nResult: success result"),
            ("test-id-123", None, "✅ Callback success sent for ID: test-id-123"),
        ]
    )
    def test_format_callback_success_message(self, callback_id, result, expected):
        """Test format_callback_success_message with and without result"""
        output = format_callback_success_message(callback_id, result)
        self.assertEqual(output, expected)

    @parameterized.expand(
        [
            (
                "test-id-123",
                "error data",
                "TypeError",
                "detailed error message",
                "❌ Callback failure sent for ID: test-id-123\nError Type: TypeError\nError Message: detailed error message\nError Data: error data",
            ),
            ("test-id-123", None, None, None, "❌ Callback failure sent for ID: test-id-123"),
            (
                "test-id-123",
                None,
                "TimeoutError",
                None,
                "❌ Callback failure sent for ID: test-id-123\nError Type: TimeoutError",
            ),
        ]
    )
    def test_format_callback_failure_message(self, callback_id, error_data, error_type, error_message, expected):
        """Test format_callback_failure_message with various error fields"""
        result = format_callback_failure_message(callback_id, error_data, error_type, error_message)
        self.assertEqual(result, expected)

    def test_format_callback_heartbeat_message(self):
        """Test heartbeat message"""
        result = format_callback_heartbeat_message("test-id-123")
        expected = "💓 Callback heartbeat sent for ID: test-id-123"
        self.assertEqual(result, expected)

    @parameterized.expand(
        [
            (
                "arn:aws:lambda:us-east-1:123456789012:function:MyFunction:execution:abc123",
                "TimeoutError",
                "Execution timed out",
                "timeout data",
                "🛑 Execution stopped: arn:aws:lambda:us-east-1:123456789012:function:MyFunction:execution:abc123\nError Type: TimeoutError\nError Message: Execution timed out\nError Data: timeout data",
            ),
            (
                "arn:aws:lambda:us-east-1:123456789012:function:MyFunction:execution:abc123",
                None,
                None,
                None,
                "🛑 Execution stopped: arn:aws:lambda:us-east-1:123456789012:function:MyFunction:execution:abc123",
            ),
            (
                "arn:aws:lambda:us-east-1:123456789012:function:MyFunction:execution:abc123",
                "CustomError",
                None,
                None,
                "🛑 Execution stopped: arn:aws:lambda:us-east-1:123456789012:function:MyFunction:execution:abc123\nError Type: CustomError",
            ),
        ]
    )
    def test_format_stop_execution_message(self, execution_arn, error_type, error_message, error_data, expected):
        """Test format_stop_execution_message with various error fields"""
        result = format_stop_execution_message(execution_arn, error_type, error_message, error_data)
        self.assertEqual(result, expected)
