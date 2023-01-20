from unittest import TestCase
from unittest.mock import patch, call
from botocore.exceptions import ClientError, EndpointConnectionError

from samcli.commands.list.stack_outputs.stack_outputs_context import StackOutputsContext
from samcli.commands.exceptions import RegionError
from samcli.commands.list.exceptions import SamListError, NoOutputsForStackError, StackDoesNotExistInRegionError


class TestStackOutputsContext(TestCase):
    @patch("samcli.commands.list.json_consumer.click.echo")
    @patch("samcli.commands.list.json_consumer.click.get_current_context")
    @patch("samcli.commands.list.cli_common.list_common_context.get_boto_client_provider_with_config")
    def test_stack_outputs_stack_exists(
        self, mock_client_provider, patched_click_get_current_context, patched_click_echo
    ):
        mock_client_provider.return_value.return_value.describe_stacks.return_value = {
            "Stacks": [{"Outputs": [{"OutputKey": "HelloWorldTest", "OutputValue": "TestVal", "Description": "Test"}]}]
        }
        with StackOutputsContext(
            stack_name="test", output="json", region="us-east-1", profile=None
        ) as stack_output_context:

            stack_output_context.run()
            expected_click_echo_calls = [
                call(
                    '[\n  {\n    "OutputKey": "HelloWorldTest",\n    "OutputValue": "TestVal",\n    "Description": "Test"\n  }\n]'
                )
            ]
            self.assertEqual(
                expected_click_echo_calls, patched_click_echo.call_args_list, "Stack and stack outputs should exist"
            )

    @patch("samcli.commands.list.json_consumer.click.echo")
    @patch("samcli.commands.list.json_consumer.click.get_current_context")
    @patch("samcli.commands.list.cli_common.list_common_context.get_boto_client_provider_with_config")
    def test_no_stack_object_in_response(
        self, mock_client_provider, patched_click_get_current_context, patched_click_echo
    ):
        mock_client_provider.return_value.return_value.describe_stacks.return_value = {"Stacks": []}
        with self.assertRaises(StackDoesNotExistInRegionError):
            with StackOutputsContext(
                stack_name="test", output="json", region="us-east-1", profile=None
            ) as stack_output_context:
                stack_output_context.run()

    @patch("samcli.commands.list.json_consumer.click.echo")
    @patch("samcli.commands.list.json_consumer.click.get_current_context")
    @patch("samcli.commands.list.cli_common.list_common_context.get_boto_client_provider_with_config")
    def test_no_output_object_in_response(
        self, mock_client_provider, patched_click_get_current_context, patched_click_echo
    ):
        mock_client_provider.return_value.return_value.describe_stacks.return_value = {"Stacks": [{}]}
        with self.assertRaises(NoOutputsForStackError):
            with StackOutputsContext(
                stack_name="test", output="json", region="us-east-1", profile=None
            ) as stack_output_context:
                stack_output_context.run()

    @patch("samcli.commands.list.json_consumer.click.echo")
    @patch("samcli.commands.list.json_consumer.click.get_current_context")
    @patch("samcli.commands.list.cli_common.list_common_context.get_boto_client_provider_with_config")
    def test_clienterror_stack_does_not_exist_in_region(
        self, mock_client_provider, patched_click_get_current_context, patched_click_echo
    ):
        mock_client_provider.return_value.return_value.describe_stacks.side_effect = ClientError(
            {"Error": {"Code": "ValidationError", "Message": "Stack with id test does not exist"}}, "DescribeStacks"
        )
        with self.assertRaises(StackDoesNotExistInRegionError):
            with StackOutputsContext(
                stack_name="test", output="json", region="us-east-1", profile=None
            ) as stack_output_context:
                stack_output_context.run()

    @patch("samcli.commands.list.json_consumer.click.echo")
    @patch("samcli.commands.list.json_consumer.click.get_current_context")
    @patch("samcli.commands.list.cli_common.list_common_context.get_boto_client_provider_with_config")
    def test_botocoreerror_invalid_region(
        self, mock_client_provider, patched_click_get_current_context, patched_click_echo
    ):
        mock_client_provider.return_value.return_value.describe_stacks.side_effect = EndpointConnectionError(
            endpoint_url="https://cloudformation.test.amazonaws.com/"
        )
        with self.assertRaises(SamListError):
            with StackOutputsContext(
                stack_name="test", output="json", region="us-east-1", profile=None
            ) as stack_output_context:
                stack_output_context.run()

    @patch("samcli.commands.list.json_consumer.click.echo")
    @patch("samcli.commands.list.json_consumer.click.get_current_context")
    @patch("boto3.Session.region_name", "us-east-1")
    def test_init_clients_has_region(self, patched_click_get_current_context, patched_click_echo):
        with StackOutputsContext(
            stack_name="test",
            output="json",
            region=None,
            profile=None,
        ) as stack_output_context:
            stack_output_context.init_clients()
            self.assertEqual(stack_output_context.region, "us-east-1")
