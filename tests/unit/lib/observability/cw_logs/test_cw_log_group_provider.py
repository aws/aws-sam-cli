from unittest import TestCase
from unittest.mock import Mock, ANY

from parameterized import parameterized

from samcli.lib.observability.cw_logs.cw_log_group_provider import LogGroupProvider


class TestLogGroupProvider_for_lambda_function(TestCase):
    def test_must_return_log_group_name(self):
        expected = "/aws/lambda/my_function_name"
        result = LogGroupProvider.for_lambda_function("my_function_name")

        self.assertEqual(expected, result)

    def test_rest_api_log_group_name(self):
        expected = "API-Gateway-Execution-Logs_my_function_name/Prod"
        result = LogGroupProvider.for_resource(Mock(), "AWS::ApiGateway::RestApi", "my_function_name")

        self.assertEqual(expected, result)

    def test_http_api_log_group_name(self):
        given_client_provider = Mock()
        given_client_provider(ANY).get_stage.return_value = {
            "AccessLogSettings": {"DestinationArn": "test:my_log_group"}
        }
        expected = "my_log_group"
        result = LogGroupProvider.for_resource(given_client_provider, "AWS::ApiGatewayV2::Api", "my_function_name")

        self.assertEqual(expected, result)

    def test_http_api_log_group_name_not_exist(self):
        given_client_provider = Mock()
        given_client_provider(ANY).get_stage.return_value = {}
        result = LogGroupProvider.for_resource(given_client_provider, "AWS::ApiGatewayV2::Api", "my_function_name")

        self.assertIsNone(result)

    def test_step_functions(self):
        given_client_provider = Mock()
        given_cw_log_group_name = "sam-app-logs-command-test-MyStateMachineLogGroup-ucwMaQpNBJTD"
        given_client_provider(ANY).describe_state_machine.return_value = {
            "loggingConfiguration": {
                "destinations": [
                    {
                        "cloudWatchLogsLogGroup": {
                            "logGroupArn": f"arn:aws:logs:us-west-2:694866504768:log-group:{given_cw_log_group_name}:*"
                        }
                    }
                ]
            }
        }

        result = LogGroupProvider.for_resource(
            given_client_provider, "AWS::StepFunctions::StateMachine", "my_state_machine"
        )

        self.assertIsNotNone(result)
        self.assertEqual(result, given_cw_log_group_name)

    def test_invalid_step_functions(self):
        given_client_provider = Mock()
        given_client_provider(ANY).describe_state_machine.return_value = {"loggingConfiguration": {"destinations": []}}

        result = LogGroupProvider.for_resource(
            given_client_provider, "AWS::StepFunctions::StateMachine", "my_state_machine"
        )

        self.assertIsNone(result)

    @parameterized.expand(["non-ARN-log-group", "invalid:log:arn"])
    def test_invalid_step_functions_configuration(self, log_group_arn):
        given_client_provider = Mock()
        given_client_provider(ANY).describe_state_machine.return_value = {
            "loggingConfiguration": {"destinations": [{"cloudWatchLogsLogGroup": {"logGroupArn": log_group_arn}}]}
        }

        result = LogGroupProvider.for_resource(
            given_client_provider, "AWS::StepFunctions::StateMachine", "my_state_machine"
        )

        self.assertIsNone(result)
