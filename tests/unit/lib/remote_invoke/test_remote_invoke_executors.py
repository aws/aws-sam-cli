import json
from pathlib import Path
from typing import List
from unittest import TestCase
from unittest.mock import Mock, patch

from samcli.lib.remote_invoke.remote_invoke_executors import (
    RemoteInvokeExecutionInfo,
    BotoActionExecutor,
    RemoteInvokeExecutor,
    ResponseObjectToJsonStringMapper,
    RemoteInvokeRequestResponseMapper,
)


class TestRemoteInvokeExecutionInfo(TestCase):
    def test_execution_info_payload(self):
        given_payload = Mock()

        test_execution_info = RemoteInvokeExecutionInfo(given_payload, None)

        self.assertEqual(given_payload, test_execution_info.payload)
        self.assertFalse(test_execution_info.is_file_provided())
        self.assertIsNone(test_execution_info.payload_file_path)

    def test_execution_info_payload_file(self):
        given_payload_file = Mock()

        test_execution_info = RemoteInvokeExecutionInfo(None, given_payload_file)

        self.assertIsNone(test_execution_info.payload)
        self.assertTrue(test_execution_info.is_file_provided())

        file_path = test_execution_info.payload_file_path

        self.assertEqual(file_path, given_payload_file)

    def test_execution_success(self):
        given_response = Mock()

        test_execution_info = RemoteInvokeExecutionInfo(None, None)
        test_execution_info.response = given_response

        self.assertTrue(test_execution_info.is_succeeded())
        self.assertEqual(test_execution_info.response, given_response)

    def test_execution_failed(self):
        given_exception = Mock()

        test_execution_info = RemoteInvokeExecutionInfo(None, None)
        test_execution_info.exception = given_exception

        self.assertFalse(test_execution_info.is_succeeded())
        self.assertEqual(test_execution_info.exception, given_exception)


class ExampleBotoActionExecutor(BotoActionExecutor):
    def _execute_action(self, payload: str) -> dict:
        return {}


class TestBotoActionExecutor(TestCase):
    def setUp(self) -> None:
        self.boto_action_executor = ExampleBotoActionExecutor()

    def test_execute_with_payload(self):
        given_payload = Mock()
        test_execution_info = RemoteInvokeExecutionInfo(given_payload, None)

        with patch.object(self.boto_action_executor, "_execute_action") as patched_execute_action, patch.object(
            self.boto_action_executor, "_execute_action_file"
        ) as patched_execute_action_file:
            given_result = Mock()
            patched_execute_action.return_value = given_result

            result = self.boto_action_executor.execute(test_execution_info)

            patched_execute_action.assert_called_with(given_payload)
            patched_execute_action_file.assert_not_called()

            self.assertEqual(given_result, result.response)

    def test_execute_with_payload_file(self):
        given_payload_file = Mock()
        test_execution_info = RemoteInvokeExecutionInfo(None, given_payload_file)

        with patch.object(self.boto_action_executor, "_execute_action") as patched_execute_action, patch.object(
            self.boto_action_executor, "_execute_action_file"
        ) as patched_execute_action_file:
            given_result = Mock()
            patched_execute_action_file.return_value = given_result

            result = self.boto_action_executor.execute(test_execution_info)

            patched_execute_action_file.assert_called_with(given_payload_file)
            patched_execute_action.assert_not_called()

            self.assertEqual(given_result, result.response)

    def test_execute_error(self):
        given_payload = Mock()
        test_execution_info = RemoteInvokeExecutionInfo(given_payload, None)

        with patch.object(self.boto_action_executor, "_execute_action") as patched_execute_action:
            given_exception = ValueError()
            patched_execute_action.side_effect = given_exception

            result = self.boto_action_executor.execute(test_execution_info)

            patched_execute_action.assert_called_with(given_payload)

            self.assertEqual(given_exception, result.exception)


class TestRemoteInvokeExecutor(TestCase):
    def setUp(self) -> None:
        self.mock_boto_action_executor = Mock()
        self.mock_request_mappers: List[RemoteInvokeRequestResponseMapper] = [
            Mock(spec=RemoteInvokeRequestResponseMapper),
            Mock(spec=RemoteInvokeRequestResponseMapper),
            Mock(spec=RemoteInvokeRequestResponseMapper),
        ]
        self.mock_response_mappers: List[RemoteInvokeRequestResponseMapper] = [
            Mock(spec=RemoteInvokeRequestResponseMapper),
            Mock(spec=RemoteInvokeRequestResponseMapper),
            Mock(spec=RemoteInvokeRequestResponseMapper),
        ]

        self.test_executor = RemoteInvokeExecutor(
            self.mock_request_mappers, self.mock_response_mappers, self.mock_boto_action_executor
        )

    def test_execution(self):
        given_payload = Mock()
        test_execution_info = RemoteInvokeExecutionInfo(given_payload, None)

        result = self.test_executor.execute(test_execution_info)

        self.assertIsNotNone(result)

        for request_mapper in self.mock_request_mappers:
            request_mapper.map.assert_called_once()

        for response_mapper in self.mock_response_mappers:
            response_mapper.map.assert_called_once()

    def test_execution_failure(self):
        given_payload = Mock()
        test_execution_info = RemoteInvokeExecutionInfo(given_payload, None)

        given_result_execution_info = RemoteInvokeExecutionInfo(given_payload, None)
        given_result_execution_info.exception = Mock()
        self.mock_boto_action_executor.execute.return_value = given_result_execution_info

        result = self.test_executor.execute(test_execution_info)

        self.assertIsNotNone(result)

        for request_mapper in self.mock_request_mappers:
            request_mapper.map.assert_called_once()

        for response_mapper in self.mock_response_mappers:
            response_mapper.map.assert_not_called()


class TestResponseObjectToJsonStringMapper(TestCase):
    def test_mapper(self):
        given_object = [{"key": "value", "key2": 123}]
        test_execution_info = RemoteInvokeExecutionInfo(None, None)
        test_execution_info.response = given_object

        mapper = ResponseObjectToJsonStringMapper()
        result = mapper.map(test_execution_info)

        self.assertEqual(result.response, json.dumps(given_object, indent=2))
