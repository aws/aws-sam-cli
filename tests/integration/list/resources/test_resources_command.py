import os
import boto3
import json
from unittest import skipIf
from tests.integration.list.resources.resources_integ_base import ResourcesIntegBase
from samcli.commands.list.resources.command import HELP_TEXT
from tests.testing_utils import CI_OVERRIDE, RUN_BY_CANARY
from tests.testing_utils import run_command, run_command_with_input, method_to_stack_name

CFN_PYTHON_VERSION_SUFFIX = os.environ.get("PYTHON_VERSION", "0.0.0").replace(".", "-")


@skipIf(
    (not RUN_BY_CANARY and not CI_OVERRIDE),
    "Skip List test cases unless running in CI",
)
class TestResources(ResourcesIntegBase):
    def setUp(self):
        self.cf_client = boto3.client("cloudformation")
        super().setUp()

    def test_resources_help_message(self):
        cmdlist = self.get_resources_command_list(help=True)
        command_result = run_command(cmdlist)
        from_command = "".join(command_result.stdout.decode().split())
        from_help = "".join(HELP_TEXT.split())
        self.assertIn(from_help, from_command, "Resources help text should have been printed")

    def test_successful_transform(self):
        template_path = self.list_test_data_path.joinpath("test_stack_creation_template.yaml")
        region = boto3.Session().region_name
        cmdlist = self.get_resources_command_list(
            stack_name=None, region=region, output="json", template_file=template_path
        )
        command_result = run_command(cmdlist, cwd=self.working_dir)
        command_output = json.loads(command_result.stdout.decode())
        self.assertEqual(len(command_output), 6)
        self.assert_resource(command_output, "HelloWorldFunction", "-")
        self.assert_resource(command_output, "HelloWorldFunctionRole", "-")
        self.assert_resource(command_output, "HelloWorldFunctionHelloWorldPermissionProd", "-")
        self.assert_resource(command_output, "ServerlessRestApi", "-")
        self.assert_resource(command_output, "ServerlessRestApiProdStage", "-")
        self.assert_resource(command_output, "ServerlessRestApiDeployment.*", "-")

    def test_invalid_template_file(self):
        template_path = self.list_test_data_path.joinpath("test_resources_invalid_sam_template.yaml")
        region = boto3.Session().region_name
        cmdlist = self.get_resources_command_list(
            stack_name=None, region=region, output="json", template_file=template_path
        )
        command_result = run_command(cmdlist, cwd=self.working_dir)
        self.assertIn(
            "Error: [InvalidTemplateException(\"'Resources' section is required\")] 'Resources' section is required",
            command_result.stderr.decode(),
        )

    def test_success_with_stack_name(self):
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

        cmdlist = self.get_resources_command_list(
            stack_name=stack_name, region=region, output="json", template_file=template_path
        )
        command_result = run_command(cmdlist, cwd=self.working_dir)
        command_output = json.loads(command_result.stdout.decode())
        self.assertEqual(len(command_output), 7)
        self.assert_resource(command_output, "HelloWorldFunction", ".*HelloWorldFunction.*")
        self.assert_resource(command_output, "HelloWorldFunctionRole", ".*HelloWorldFunctionRole.*")
        self.assert_resource(
            command_output,
            "HelloWorldFunctionHelloWorldPermissionProd",
            ".*HelloWorldFunctionHelloWorldPermissionProd.*",
        )
        self.assert_resource(command_output, "ServerlessRestApi", ".*")
        self.assert_resource(command_output, "ServerlessRestApiProdStage", ".*")
        self.assert_resource(command_output, "ServerlessRestApiDeployment.*", ".*")

    def test_stack_does_not_exist(self):
        template_path = self.list_test_data_path.joinpath("test_stack_creation_template.yaml")
        stack_name = method_to_stack_name(self.id())
        region = boto3.Session().region_name
        cmdlist = self.get_resources_command_list(
            stack_name=stack_name, region=region, output="json", template_file=template_path
        )
        command_result = run_command(cmdlist, cwd=self.working_dir)
        expected_output = (
            f"Error: The input stack {stack_name} does" f" not exist on Cloudformation in the region {region}"
        )
        self.assertIn(
            expected_output, command_result.stderr.decode(), "Should have raised error that outputs do not exist"
        )
