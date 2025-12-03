"""
Unit tests for samcli.lib.clients.lambda_client module.
"""

import os
import sys
import unittest
from unittest.mock import MagicMock, Mock, patch, call

import boto3
from botocore.exceptions import ClientError

from samcli.lib.clients.lambda_client import DurableFunctionsClient
from samcli.local.lambdafn.exceptions import DurableExecutionNotFound


class TestDurableFunctionsClient(unittest.TestCase):
    """Test cases for DurableFunctionsClient class."""

    def test_init_with_client(self):
        """Test DurableFunctionsClient initialization with client."""
        # Arrange
        mock_client = MagicMock()

        # Act
        client = DurableFunctionsClient(mock_client)

        # Assert
        self.assertEqual(client.client, mock_client)

    @patch("samcli.lib.clients.lambda_client.botocore.session.Session")
    def test_create_default_parameters(self, mock_session_class):
        """Test DurableFunctionsClient.create() with default parameters."""
        # Arrange
        mock_client = MagicMock()
        mock_session = MagicMock()
        mock_session.create_client.return_value = mock_client
        mock_session_class.return_value = mock_session

        # Act
        client = DurableFunctionsClient.create()

        # Assert
        self.assertEqual(client.client, mock_client)
        mock_session_class.assert_called_once()
        mock_session.create_client.assert_called_once_with(
            "lambda", endpoint_url="http://localhost:5000", region_name="us-west-2"
        )

    @patch("samcli.lib.clients.lambda_client.botocore.session.Session")
    def test_create_custom_parameters(self, mock_session_class):
        """Test DurableFunctionsClient.create() with custom parameters."""
        # Arrange
        mock_client = MagicMock()
        mock_session = MagicMock()
        mock_session.create_client.return_value = mock_client
        mock_session_class.return_value = mock_session
        custom_host = "custom-host"
        custom_port = 8080
        custom_region = "us-east-1"

        # Act
        client = DurableFunctionsClient.create(host=custom_host, port=custom_port, region=custom_region)

        # Assert
        self.assertEqual(client.client, mock_client)
        mock_session_class.assert_called_once()
        mock_session.create_client.assert_called_once_with(
            "lambda",
            endpoint_url=f"http://{custom_host}:{custom_port}",
            region_name=custom_region,
        )

    @patch("samcli.lib.clients.lambda_client.botocore.session.Session")
    def test_create_failure(self, mock_session_class):
        """Test client creation failure."""
        # Arrange
        mock_session = MagicMock()
        mock_session.create_client.side_effect = Exception("Connection failed")
        mock_session_class.return_value = mock_session

        # Act & Assert
        with self.assertRaises(Exception) as context:
            DurableFunctionsClient.create()

        self.assertIn("Connection failed", str(context.exception))

    def test_send_callback_success_with_result(self):
        """Test sending a success callback with result."""
        # Arrange
        mock_client = MagicMock()
        mock_response = {"ResponseMetadata": {"HTTPStatusCode": 200}, "CallbackId": "test-callback-id"}
        mock_client.send_durable_execution_callback_success.return_value = mock_response

        client = DurableFunctionsClient(mock_client)
        callback_id = "test-callback-id"
        result = "success result"

        # Act
        response = client.send_callback_success(callback_id, result)

        # Assert
        mock_client.send_durable_execution_callback_success.assert_called_once_with(
            CallbackId=callback_id, Result=result.encode("utf-8")
        )
        expected_response = {"CallbackId": "test-callback-id"}
        self.assertEqual(response, expected_response)
        self.assertNotIn("ResponseMetadata", response)

    def test_send_callback_success_without_result(self):
        """Test sending a success callback without result."""
        # Arrange
        mock_client = MagicMock()
        mock_response = {"ResponseMetadata": {"HTTPStatusCode": 200}, "CallbackId": "test-callback-id"}
        mock_client.send_durable_execution_callback_success.return_value = mock_response

        client = DurableFunctionsClient(mock_client)
        callback_id = "test-callback-id"

        # Act
        response = client.send_callback_success(callback_id)

        # Assert
        mock_client.send_durable_execution_callback_success.assert_called_once_with(CallbackId=callback_id)
        expected_response = {"CallbackId": "test-callback-id"}
        self.assertEqual(response, expected_response)
        self.assertNotIn("ResponseMetadata", response)

    def test_send_callback_failure_with_all_new_parameters(self):
        """Test sending a failure callback with all new error parameters."""
        # Arrange
        mock_client = MagicMock()
        mock_response = {"ResponseMetadata": {"HTTPStatusCode": 200}, "CallbackId": "test-callback-id"}
        mock_client.send_durable_execution_callback_failure.return_value = mock_response

        client = DurableFunctionsClient(mock_client)
        callback_id = "test-callback-id"
        error_data = "Additional error data"
        stack_trace = ["Stack trace line 1", "Stack trace line 2"]
        error_type = "TypeError"
        error_message = "Detailed error message"

        # Act
        response = client.send_callback_failure(
            callback_id,
            error_data=error_data,
            stack_trace=stack_trace,
            error_type=error_type,
            error_message=error_message,
        )

        # Assert
        mock_client.send_durable_execution_callback_failure.assert_called_once_with(
            CallbackId=callback_id,
            Error={
                "ErrorData": error_data,
                "StackTrace": stack_trace,
                "ErrorType": error_type,
                "ErrorMessage": error_message,
            },
        )
        expected_response = {"CallbackId": "test-callback-id"}
        self.assertEqual(response, expected_response)
        self.assertNotIn("ResponseMetadata", response)

    def test_send_callback_failure_with_partial_parameters(self):
        """Test sending a failure callback with some new parameters."""
        # Arrange
        mock_client = MagicMock()
        mock_response = {"ResponseMetadata": {"HTTPStatusCode": 200}, "CallbackId": "test-callback-id"}
        mock_client.send_durable_execution_callback_failure.return_value = mock_response

        client = DurableFunctionsClient(mock_client)
        callback_id = "test-callback-id"
        error_type = "TypeError"
        error_message = "Something went wrong"

        # Act
        response = client.send_callback_failure(callback_id, error_type=error_type, error_message=error_message)

        # Assert
        mock_client.send_durable_execution_callback_failure.assert_called_once_with(
            CallbackId=callback_id, Error={"ErrorType": error_type, "ErrorMessage": error_message}
        )
        expected_response = {"CallbackId": "test-callback-id"}
        self.assertEqual(response, expected_response)
        self.assertNotIn("ResponseMetadata", response)

    def test_send_callback_failure_without_parameters(self):
        """Test sending a failure callback without any error parameters."""
        # Arrange
        mock_client = MagicMock()
        mock_response = {"ResponseMetadata": {"HTTPStatusCode": 200}, "CallbackId": "test-callback-id"}
        mock_client.send_durable_execution_callback_failure.return_value = mock_response

        client = DurableFunctionsClient(mock_client)
        callback_id = "test-callback-id"

        # Act
        response = client.send_callback_failure(callback_id)

        # Assert
        mock_client.send_durable_execution_callback_failure.assert_called_once_with(CallbackId=callback_id, Error={})
        expected_response = {"CallbackId": "test-callback-id"}
        self.assertEqual(response, expected_response)
        self.assertNotIn("ResponseMetadata", response)

    def test_send_callback_heartbeat(self):
        """Test sending a heartbeat callback."""
        # Arrange
        mock_client = MagicMock()
        mock_response = {"ResponseMetadata": {"HTTPStatusCode": 200}, "CallbackId": "test-callback-id"}
        mock_client.send_durable_execution_callback_heartbeat.return_value = mock_response

        client = DurableFunctionsClient(mock_client)
        callback_id = "test-callback-id"

        # Act
        response = client.send_callback_heartbeat(callback_id)

        # Assert
        mock_client.send_durable_execution_callback_heartbeat.assert_called_once_with(CallbackId=callback_id)
        expected_response = {"CallbackId": "test-callback-id"}
        self.assertEqual(response, expected_response)
        self.assertNotIn("ResponseMetadata", response)

    def test_get_durable_execution(self):
        """Test getting durable execution details"""
        durable_execution_arn = (
            "arn:aws:lambda:us-west-2:123456789012:function:test-function:$LATEST:durable-execution:test-123"
        )

        # Mock the boto3 client
        mock_client = Mock()
        mock_client.get_durable_execution.return_value = {
            "DurableExecutionArn": durable_execution_arn,
            "Status": "SUCCEEDED",
            "ResponseMetadata": {"HTTPStatusCode": 200},
        }

        client = DurableFunctionsClient(mock_client)
        result = client.get_durable_execution(durable_execution_arn)

        # Verify the client method was called correctly
        mock_client.get_durable_execution.assert_called_once_with(DurableExecutionArn=durable_execution_arn)

        # Verify the result - ResponseMetadata should be stripped
        self.assertIsInstance(result, dict)
        self.assertEqual(result["DurableExecutionArn"], durable_execution_arn)
        self.assertEqual(result["Status"], "SUCCEEDED")
        self.assertNotIn("ResponseMetadata", result)

    def test_get_durable_execution_exception(self):
        """Test get durable execution with client exception"""
        durable_execution_arn = (
            "arn:aws:lambda:us-west-2:123456789012:function:test-function:$LATEST:durable-execution:test-123"
        )

        # Mock the boto3 client to raise an exception
        mock_client = Mock()
        mock_client.get_durable_execution.side_effect = Exception("Client error")

        client = DurableFunctionsClient(mock_client)
        with self.assertRaises(Exception) as context:
            client.get_durable_execution(durable_execution_arn)

        self.assertEqual(str(context.exception), "Client error")

    def test_get_durable_execution_resource_not_found(self):
        """Test get durable execution with ResourceNotFoundException"""
        durable_execution_arn = (
            "arn:aws:lambda:us-west-2:123456789012:function:test-function:$LATEST:durable-execution:test-123"
        )

        # Mock the boto3 client to raise ResourceNotFoundException
        mock_client = Mock()
        error_response = {"Error": {"Code": "ResourceNotFoundException", "Message": "Not found"}}
        mock_client.get_durable_execution.side_effect = ClientError(error_response, "GetDurableExecution")

        client = DurableFunctionsClient(mock_client)
        with self.assertRaises(DurableExecutionNotFound) as context:
            client.get_durable_execution(durable_execution_arn)

        self.assertIn("Durable execution not found", str(context.exception))

    def test_get_durable_execution_history(self):
        """Test getting durable execution history"""
        durable_execution_arn = (
            "arn:aws:lambda:us-west-2:123456789012:function:test-function:$LATEST:durable-execution:test-123"
        )

        # Mock the boto3 client
        mock_client = Mock()
        mock_client.get_durable_execution_history.return_value = {
            "DurableExecutionArn": durable_execution_arn,
            "Events": [
                {
                    "Timestamp": "2024-01-01T00:00:00Z",
                    "Type": "ExecutionStarted",
                    "Details": {"Input": '{"test": "input"}'},
                }
            ],
            "ResponseMetadata": {"HTTPStatusCode": 200},
        }

        client = DurableFunctionsClient(mock_client)
        result = client.get_durable_execution_history(durable_execution_arn)

        # Verify the client method was called correctly
        mock_client.get_durable_execution_history.assert_called_once_with(
            DurableExecutionArn=durable_execution_arn, IncludeExecutionData=True
        )

        # Verify the result - ResponseMetadata should be stripped
        self.assertIsInstance(result, dict)
        self.assertEqual(result["DurableExecutionArn"], durable_execution_arn)
        self.assertEqual(len(result["Events"]), 1)
        self.assertEqual(result["Events"][0]["Type"], "ExecutionStarted")
        self.assertNotIn("ResponseMetadata", result)

    def test_get_durable_execution_history_include_execution_data(self):
        """Test getting durable execution history"""
        durable_execution_arn = (
            "arn:aws:lambda:us-west-2:123456789012:function:test-function:$LATEST:durable-execution:test-123"
        )

        # Mock the boto3 client
        mock_client = Mock()
        mock_client.get_durable_execution_history.return_value = {
            "DurableExecutionArn": durable_execution_arn,
            "Events": [
                {
                    "Timestamp": "2024-01-01T00:00:00Z",
                    "Type": "ExecutionStarted",
                    "Details": {"Input": '{"test": "input"}'},
                }
            ],
            "ResponseMetadata": {"HTTPStatusCode": 200},
        }

        client = DurableFunctionsClient(mock_client)
        result = client.get_durable_execution_history(durable_execution_arn, True)

        # Verify the client method was called correctly
        mock_client.get_durable_execution_history.assert_called_once_with(
            DurableExecutionArn=durable_execution_arn, IncludeExecutionData=True
        )

        # Verify the result - ResponseMetadata should be stripped
        self.assertIsInstance(result, dict)
        self.assertEqual(result["DurableExecutionArn"], durable_execution_arn)
        self.assertEqual(len(result["Events"]), 1)
        self.assertEqual(result["Events"][0]["Type"], "ExecutionStarted")
        self.assertNotIn("ResponseMetadata", result)

    def test_get_durable_execution_history_exception(self):
        """Test get durable execution history with client exception"""
        durable_execution_arn = (
            "arn:aws:lambda:us-west-2:123456789012:function:test-function:$LATEST:durable-execution:test-123"
        )

        # Mock the boto3 client to raise an exception
        mock_client = Mock()
        mock_client.get_durable_execution_history.side_effect = Exception("History client error")

        client = DurableFunctionsClient(mock_client)
        with self.assertRaises(Exception) as context:
            client.get_durable_execution_history(durable_execution_arn)

        self.assertEqual(str(context.exception), "History client error")

    def test_get_durable_execution_history_resource_not_found(self):
        """Test get durable execution history with ResourceNotFoundException"""
        durable_execution_arn = (
            "arn:aws:lambda:us-west-2:123456789012:function:test-function:$LATEST:durable-execution:test-123"
        )

        # Mock the boto3 client to raise ResourceNotFoundException
        mock_client = Mock()
        error_response = {"Error": {"Code": "ResourceNotFoundException", "Message": "Not found"}}
        mock_client.get_durable_execution_history.side_effect = ClientError(
            error_response, "GetDurableExecutionHistory"
        )

        client = DurableFunctionsClient(mock_client)
        with self.assertRaises(DurableExecutionNotFound) as context:
            client.get_durable_execution_history(durable_execution_arn)

        self.assertIn("Durable execution not found", str(context.exception))
