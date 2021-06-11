from unittest import TestCase
from unittest.mock import Mock, patch

from samcli.lib.observability.cw_logs.cw_log_group_provider import LogGroupProvider


class TestLogGroupProvider_for_lambda_function(TestCase):
    def test_must_return_log_group_name(self):
        expected = "/aws/lambda/my_function_name"
        result = LogGroupProvider.for_lambda_function("my_function_name")

        self.assertEqual(expected, result)

    def test_rest_api_log_group_name(self):
        expected = "API-Gateway-Execution-Logs_my_function_name/Prod"
        result = LogGroupProvider.for_resource("AWS::ApiGateway::RestApi", "my_function_name")

        self.assertEqual(expected, result)

    @patch("boto3.client")
    def test_http_api_log_group_name(self, patched_client):
        patched_client().get_stage.return_value = {"AccessLogSettings": {"DestinationArn": "test:my_log_group"}}
        expected = "my_log_group"
        result = LogGroupProvider.for_resource("AWS::ApiGatewayV2::Api", "my_function_name")

        self.assertEqual(expected, result)

    @patch("boto3.client")
    def test_http_api_log_group_name_not_exist(self, patched_client):
        patched_client().get_stage.return_value = {}
        result = LogGroupProvider.for_resource("AWS::ApiGatewayV2::Api", "my_function_name")

        self.assertIsNone(result)
