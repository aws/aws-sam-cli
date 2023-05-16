import os
import boto3
import json
from unittest import skipIf

from tests.integration.list.stack_outputs.stack_outputs_integ_base import StackOutputsIntegBase
from samcli.commands.list.stack_outputs.command import HELP_TEXT
from tests.testing_utils import CI_OVERRIDE, RUN_BY_CANARY
from tests.testing_utils import run_command, run_command_with_input, method_to_stack_name

CFN_PYTHON_VERSION_SUFFIX = os.environ.get("PYTHON_VERSION", "0.0.0").replace(".", "-")


@skipIf(
    (not RUN_BY_CANARY and not CI_OVERRIDE),
    "Skip List test cases unless running in CI",
)
class TestStackOutputs(StackOutputsIntegBase):
    def setUp(self):
        self.cf_client = boto3.client("cloudformation")
        super().setUp()

    def test_stack_outputs_help_message(self):
        cmdlist = self.get_stack_outputs_command_list(help=True)
        command_result = run_command(cmdlist, cwd=self.working_dir)
        from_command = "".join(command_result.stdout.decode().split())
        from_help = "".join(HELP_TEXT.split())
        self.assertIn(from_help, from_command, "Stack-outputs help text should have been printed")

    def test_stack_output_exists(self):
        template_path = self.list_test_data_path.joinpath("test_stack_creation_template.yaml")
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
            deploy_command_list, "{}\n{}\nY\nY\nY\nY\nY\n\n\nY\n".format(stack_name, region).encode()
        )
        self.stacks.append({"name": stack_name})

        cmdlist = self.get_stack_outputs_command_list(stack_name=stack_name, region=region, output="json")
        command_result = run_command(cmdlist, cwd=self.working_dir)
        outputs = json.loads(command_result.stdout.decode())
        self.assertEqual(len(outputs), 3)
        self.check_stack_output(
            outputs[0],
            "HelloWorldFunctionIamRole",
            "arn:aws:iam::.*:role/.*-HelloWorldFunctionRole\\-.*",
            "Implicit IAM Role created for Hello World function",
        )
        self.check_stack_output(
            outputs[1],
            "HelloWorldApi",
            "https://.*execute.*\\.amazonaws.com/Prod/hello/",
            "",
        )
        self.check_stack_output(
            outputs[2],
            "HelloWorldFunction",
            "arn:aws:lambda:.*:.*:function:.*-HelloWorldFunction\\-.*",
            "Hello World Lambda Function ARN",
        )

    def test_stack_no_outputs_exist(self):
        template_path = self.list_test_data_path.joinpath("test_stack_no_outputs_template.yaml")
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
            deploy_command_list, "{}\n{}\nY\nY\nY\nY\nY\n\n\nY\n".format(stack_name, region).encode()
        )
        self.stacks.append({"name": stack_name})

        cmdlist = self.get_stack_outputs_command_list(stack_name=stack_name, region=region, output="json")
        command_result = run_command(cmdlist, cwd=self.working_dir)
        expected_output = (
            f"Error: Outputs do not exist for the input stack {stack_name}" f" on Cloudformation in the region {region}"
        )
        self.assertIn(
            expected_output, command_result.stderr.decode(), "Should have raised error that outputs do not exist"
        )

    def test_stack_does_not_exist(self):
        stack_name = method_to_stack_name(self.id())
        region = boto3.Session().region_name
        cmdlist = self.get_stack_outputs_command_list(stack_name=stack_name, region=region, output="json")
        command_result = run_command(cmdlist, cwd=self.working_dir)
        expected_output = (
            f"Error: The input stack {stack_name} does" f" not exist on Cloudformation in the region {region}"
        )
        self.assertIn(
            expected_output, command_result.stderr.decode(), "Should have raised error that outputs do not exist"
        )
