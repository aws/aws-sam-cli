import os
import boto3
import json
from unittest import skipIf
from tests.integration.list.endpoints.endpoints_integ_base import EndpointsIntegBase
from samcli.commands.list.endpoints.command import HELP_TEXT
from tests.testing_utils import CI_OVERRIDE, RUN_BY_CANARY
from tests.testing_utils import run_command, run_command_with_input, method_to_stack_name

CFN_PYTHON_VERSION_SUFFIX = os.environ.get("PYTHON_VERSION", "0.0.0").replace(".", "-")


@skipIf(
    (not RUN_BY_CANARY and not CI_OVERRIDE),
    "Skip List test cases unless running in CI",
)
class TestEndpoints(EndpointsIntegBase):
    def test_endpoints_help_message(self):
        cmdlist = self.get_endpoints_command_list(help=True)
        command_result = run_command(cmdlist)
        from_command = "".join(command_result.stdout.decode().split())
        from_help = "".join(HELP_TEXT.split())
        self.assertIn(from_help, from_command, "Endpoints help text should have been printed")

    def test_no_stack_name(self):
        template_path = self.list_test_data_path.joinpath("test_endpoints_template.yaml")
        region = boto3.Session().region_name
        cmdlist = self.get_endpoints_command_list(
            stack_name=None, output="json", region=region, template_file=template_path
        )
        command_result = run_command(cmdlist, cwd=self.working_dir)
        command_output = json.loads(command_result.stdout.decode())
        self.assertEqual(len(command_output), 3)
        self.assert_endpoints(command_output, "HelloWorldFunction", "-", "-", "-")
        self.assert_endpoints(
            command_output,
            "ServerlessRestApi",
            "-",
            [],
            ["/hello2['get']", "/hello['get']"],
        )
        self.assert_endpoints(command_output, "TestAPI", "-", "-", [])

    def test_has_stack_name(self):
        template_path = self.list_test_data_path.joinpath("test_endpoints_template.yaml")
        stack_name = method_to_stack_name(self.id())
        region = boto3.Session().region_name
        deploy_command_list = self.get_deploy_command_list(
            template_file=template_path,
            guided=True,
            region=region,
            confirm_changeset=True,
            disable_rollback=True,
        )
        run_command_with_input(
            deploy_command_list, "{}\n{}\nY\nY\nY\nY\nY\nY\n\n\nY\n".format(stack_name, region).encode()
        )
        self.stacks.append({"name": stack_name})

        cmdlist = self.get_endpoints_command_list(
            stack_name=stack_name, output="json", region=region, template_file=template_path
        )
        command_result = run_command(cmdlist, cwd=self.working_dir)
        command_output = json.loads(command_result.stdout.decode())
        self.assertEqual(len(command_output), 3)
        self.assert_endpoints(
            command_output, "HelloWorldFunction", "test-has-stack-name.*", "https://.*.lambda-url..*.on.aws/", "-"
        )
        self.assert_endpoints(
            command_output,
            "ServerlessRestApi",
            ".*",
            ["https://.*.execute-api..*.amazonaws.com/Prod", "https://.*.execute-api..*.amazonaws.com/Stage"],
            ["/hello2['get']", "/hello['get']"],
        )
        self.assert_endpoints(command_output, "TestAPI", ".*", ["https://.*.execute-api..*.amazonaws.com/Test2"], [])

    def test_stack_does_not_exist(self):
        template_path = self.list_test_data_path.joinpath("test_endpoints_template.yaml")
        stack_name = method_to_stack_name(self.id())
        region = boto3.Session().region_name
        cmdlist = self.get_endpoints_command_list(
            stack_name=stack_name, output="json", region=region, template_file=template_path
        )
        command_result = run_command(cmdlist, cwd=self.working_dir)
        expected_output = (
            f"Error: The input stack {stack_name} does" f" not exist on Cloudformation in the region {region}"
        )
        self.assertIn(
            expected_output, command_result.stderr.decode(), "Should have raised error that outputs do not exist"
        )
