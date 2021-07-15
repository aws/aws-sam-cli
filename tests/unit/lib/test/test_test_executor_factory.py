from unittest import TestCase
from unittest.mock import patch, Mock

from samcli.lib.test.test_executor_factory import TestExecutorFactory


class TestTestExecutorFactory(TestCase):
    def setUp(self) -> None:
        self.boto_client_provider_mock = Mock()
        self.test_executor_factory = TestExecutorFactory(self.boto_client_provider_mock)

    @patch("samcli.lib.test.test_executor_factory.TestExecutorFactory.EXECUTOR_MAPPING")
    def test_create_test_executor(self, patched_executor_mapping):
        given_executor_creator_method = Mock()
        patched_executor_mapping.get.return_value = given_executor_creator_method

        given_executor = Mock()
        given_executor_creator_method.return_value = given_executor

        given_cfn_resource_summary = Mock()
        executor = self.test_executor_factory.create_test_executor(given_cfn_resource_summary)

        patched_executor_mapping.get.assert_called_with(given_cfn_resource_summary.resource_type)
        given_executor_creator_method.assert_called_with(self.test_executor_factory, given_cfn_resource_summary)
        self.assertEqual(executor, given_executor)

    def test_failed_create_test_executor(self):
        given_cfn_resource_summary = Mock()
        executor = self.test_executor_factory.create_test_executor(given_cfn_resource_summary)
        self.assertIsNone(executor)

    @patch("samcli.lib.test.test_executor_factory.LambdaInvokeExecutor")
    @patch("samcli.lib.test.test_executor_factory.LambdaConvertToDefaultJSON")
    @patch("samcli.lib.test.test_executor_factory.LambdaResponseConverter")
    @patch("samcli.lib.test.test_executor_factory.ResponseObjectToJsonStringMapper")
    @patch("samcli.lib.test.test_executor_factory.TestExecutor")
    def test_create_lambda_test_executor(
        self,
        patched_test_executor,
        patched_object_to_json_converter,
        patched_response_converter,
        patched_convert_to_default_json,
        patched_lambda_invoke_executor,
    ):
        given_physical_resource_id = "physical_resource_id"
        given_cfn_resource_summary = Mock(physical_resource_id="physical_resource_id")

        given_lambda_client = Mock()
        self.boto_client_provider_mock.return_value = given_lambda_client

        given_test_executor = Mock()
        patched_test_executor.return_value = given_test_executor

        lambda_executor = self.test_executor_factory._create_lambda_test_executor(given_cfn_resource_summary)

        self.assertEqual(lambda_executor, given_test_executor)

        patched_convert_to_default_json.assert_called_once()
        patched_response_converter.assert_called_once()

        self.boto_client_provider_mock.assert_called_with("lambda")
        patched_lambda_invoke_executor.assert_called_with(given_lambda_client, given_physical_resource_id)

        patched_test_executor.assert_called_with(
            request_mappers=[patched_convert_to_default_json()],
            response_mappers=[patched_response_converter(), patched_object_to_json_converter()],
            boto_action_executor=patched_lambda_invoke_executor(),
        )

    @patch("samcli.lib.test.test_executor_factory.SqsSendMessageExecutor")
    @patch("samcli.lib.test.test_executor_factory.ResponseObjectToJsonStringMapper")
    @patch("samcli.lib.test.test_executor_factory.SqsConvertToEntriesJsonObject")
    @patch("samcli.lib.test.test_executor_factory.TestExecutor")
    def test_create_sqs_test_executor(
        self,
        patched_test_executor,
        patched_convert_to_json,
        patched_convert_response_to_string,
        patched_sqs_message_executor,
    ):
        given_physical_resource_id = "physical_resource_id"
        given_cfn_resource_summary = Mock(physical_resource_id="physical_resource_id")

        given_sqs_client = Mock()
        self.boto_client_provider_mock.return_value = given_sqs_client

        given_test_executor = Mock()
        patched_test_executor.return_value = given_test_executor

        lambda_executor = self.test_executor_factory._create_sqs_test_executor(given_cfn_resource_summary)

        self.assertEqual(lambda_executor, given_test_executor)

        patched_convert_to_json.assert_called_once()
        patched_convert_response_to_string.assert_called_once()

        self.boto_client_provider_mock.assert_called_with("sqs")
        patched_sqs_message_executor.assert_called_with(given_sqs_client, given_physical_resource_id)

        patched_test_executor.assert_called_with(
            request_mappers=[
                patched_convert_to_json(),
            ],
            response_mappers=[patched_convert_response_to_string()],
            boto_action_executor=patched_sqs_message_executor(),
        )
