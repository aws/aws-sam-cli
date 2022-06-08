from unittest import TestCase, mock
from unittest.mock import patch, call, MagicMock
from botocore.exceptions import ClientError, BotoCoreError, WaiterError, EndpointConnectionError
import boto3

import click

from samcli.commands.list.stack_outputs.stack_outputs_context import StackOutputsContext
from samcli.commands.list.exceptions import NoRegionError


class TestStackOutputsContext(TestCase):
    @patch("samcli.commands.list.stack_outputs.stack_outputs_context.click.echo")
    @patch("samcli.commands.list.stack_outputs.stack_outputs_context.click.get_current_context")
    @patch.object(
        StackOutputsContext,
        "stack_exists",
        MagicMock(
            return_value=(
                False,
                f"Error: The input stack test does" f" not exist on Cloudformation in the region us-east-1",
            )
        ),
    )
    def test_stack_outputs_stack_does_not_exist(self, patched_click_get_current_context, patched_click_echo):
        with StackOutputsContext(
            stack_name="test", output="json", region="us-east-1", profile="test"
        ) as stack_output_context:
            stack_output_context.run()

            expected_click_echo_calls = [
                call(f"Error: The input stack test does" + f" not exist on Cloudformation in the region us-east-1"),
            ]
            self.assertEqual(
                expected_click_echo_calls,
                patched_click_echo.call_args_list,
                "The input stack should not exist in the given region",
            )

    @patch("samcli.commands.list.stack_outputs.stack_outputs_context.click.echo")
    @patch("samcli.commands.list.stack_outputs.stack_outputs_context.click.get_current_context")
    @patch.object(
        StackOutputsContext,
        "get_stack_info",
        MagicMock(
            return_value=(
                {
                    "Stacks": [
                        {"Outputs": [{"OutputKey": "HelloWorldTest", "OutputValue": "TestVal", "Description": "Test"}]}
                    ]
                }
            )
        ),
    )
    def test_stack_outputs_stack_exists(self, patched_click_get_current_context, patched_click_echo):
        with StackOutputsContext(
            stack_name="test", output="json", region="us-east-1", profile="test"
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

    @patch("samcli.commands.list.stack_outputs.stack_outputs_context.click.echo")
    @patch("samcli.commands.list.stack_outputs.stack_outputs_context.click.get_current_context")
    @patch.object(
        StackOutputsContext,
        "get_stack_info",
        MagicMock(return_value=({"Stacks": []})),
    )
    def test_no_stack_object_in_response(self, patched_click_get_current_context, patched_click_echo):
        with StackOutputsContext(
            stack_name="test", output="json", region="us-east-1", profile="test"
        ) as stack_output_context:
            stack_output_context.run()
            expected_click_echo_calls = [
                call("Error: The input stack test does not exist on Cloudformation in the region us-east-1")
            ]
            self.assertEqual(
                expected_click_echo_calls,
                patched_click_echo.call_args_list,
                "Input stack should not exist in the given region",
            )

    @patch("samcli.commands.list.stack_outputs.stack_outputs_context.click.echo")
    @patch("samcli.commands.list.stack_outputs.stack_outputs_context.click.get_current_context")
    @patch.object(
        StackOutputsContext,
        "get_stack_info",
        MagicMock(return_value=({"Stacks": [{}]})),
    )
    def test_no_output_object_in_response(self, patched_click_get_current_context, patched_click_echo):
        with StackOutputsContext(
            stack_name="test", output="json", region="us-east-1", profile="test"
        ) as stack_output_context:
            stack_output_context.run()
            expected_click_echo_calls = [
                call("Error: Outputs do not exist for the input stack test on Cloudformation in the region us-east-1")
            ]
            self.assertEqual(
                expected_click_echo_calls, patched_click_echo.call_args_list, "Outputs should not exist for this stack"
            )

    @patch("samcli.commands.list.stack_outputs.stack_outputs_context.click.echo")
    @patch("samcli.commands.list.stack_outputs.stack_outputs_context.click.get_current_context")
    @patch.object(
        StackOutputsContext,
        "get_stack_info",
        MagicMock(
            side_effect=ClientError(
                {"Error": {"Code": "ValidationError", "Message": "Stack with id test does not exist"}}, "DescribeStacks"
            )
        ),
    )
    def test_clienterror_stack_does_not_exist_in_region(self, patched_click_get_current_context, patched_click_echo):
        with StackOutputsContext(
            stack_name="test", output="json", region="us-east-1", profile="test"
        ) as stack_output_context:
            stack_output_context.run()

            expected_click_echo_calls = [
                call(f"Error: The input stack test does" + f" not exist on Cloudformation in the region us-east-1"),
            ]
            self.assertEqual(
                expected_click_echo_calls, patched_click_echo.call_args_list, "The input stack should not exists"
            )

    @patch("samcli.commands.list.stack_outputs.stack_outputs_context.click.echo")
    @patch("samcli.commands.list.stack_outputs.stack_outputs_context.click.get_current_context")
    @patch.object(
        StackOutputsContext,
        "get_stack_info",
        MagicMock(side_effect=EndpointConnectionError(endpoint_url="https://cloudformation.test.amazonaws.com/")),
    )
    def test_botocoreerror_invalid_region(self, patched_click_get_current_context, patched_click_echo):
        with StackOutputsContext(
            stack_name="test", output="json", region="us-east-1", profile="test"
        ) as stack_output_context:
            # patched_click_echo.raiseError.side_effect = Mock(side_effect=Exception('Test'))
            stack_output_context.run()

            expected_click_echo_calls = [
                call('Error: Could not connect to the endpoint URL: "https://cloudformation.test.amazonaws.com/"'),
            ]
            self.assertEqual(
                expected_click_echo_calls, patched_click_echo.call_args_list, "Should raise endpoint connection error"
            )

    @patch("samcli.commands.list.stack_outputs.stack_outputs_context.click.echo")
    @patch("samcli.commands.list.stack_outputs.stack_outputs_context.click.get_current_context")
    @patch("boto3.Session.region_name", None)
    def test_init_clients_no_region(self, patched_click_get_current_context, patched_click_echo):
        with self.assertRaises(NoRegionError):
            with StackOutputsContext(
                stack_name="test", output="json", region=None, profile="test"
            ) as stack_output_context:
                stack_output_context.init_clients()

    @patch("samcli.commands.list.stack_outputs.stack_outputs_context.click.echo")
    @patch("samcli.commands.list.stack_outputs.stack_outputs_context.click.get_current_context")
    @patch("boto3.Session.region_name", "us-east-1")
    def test_init_clients_has_region(self, patched_click_get_current_context, patched_click_echo):
        with StackOutputsContext(stack_name="test", output="json", region=None, profile="test") as stack_output_context:
            stack_output_context.init_clients()
            self.assertTrue(stack_output_context.region)
