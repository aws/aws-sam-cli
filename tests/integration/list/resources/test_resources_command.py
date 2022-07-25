import os
import time
import boto3
import re
from unittest import skipIf
from tests.integration.deploy.deploy_integ_base import DeployIntegBase
from tests.integration.list.resources.resources_integ_base import ResourcesIntegBase
from samcli.commands.list.resources.cli import HELP_TEXT
from tests.testing_utils import RUNNING_ON_CI, RUNNING_TEST_FOR_MASTER_ON_CI, RUN_BY_CANARY
from tests.testing_utils import run_command, run_command_with_input, method_to_stack_name

SKIP_STACK_OUTPUTS_TESTS = RUNNING_ON_CI and RUNNING_TEST_FOR_MASTER_ON_CI and not RUN_BY_CANARY
CFN_SLEEP = 3
CFN_PYTHON_VERSION_SUFFIX = os.environ.get("PYTHON_VERSION", "0.0.0").replace(".", "-")


@skipIf(SKIP_STACK_OUTPUTS_TESTS, "Skip stack-outputs tests in CI/CD only")
class TestResources(DeployIntegBase, ResourcesIntegBase):
    @classmethod
    def setUpClass(cls):
        DeployIntegBase.setUpClass()
        ResourcesIntegBase.setUpClass()

    def setUp(self):
        self.cf_client = boto3.client("cloudformation")
        time.sleep(CFN_SLEEP)
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
        expression_list = [
            """{\n    "LogicalResourceId": "HelloWorldFunction",\n    "PhysicalResourceId": "-"\n  }""",
            """{\n    "LogicalResourceId": "HelloWorldFunctionRole",\n    "PhysicalResourceId": "-"\n  }""",
            """{\n    "LogicalResourceId": "HelloWorldFunctionHelloWorldPermissionProd",\n    "PhysicalResourceId": "-"\n  }""",
            """{\n    "LogicalResourceId": "ServerlessRestApi",\n    "PhysicalResourceId": "-"\n  }""",
            """{\n    "LogicalResourceId": "ServerlessRestApiProdStage",\n    "PhysicalResourceId": "-"\n  }""",
        ]
        for expression in expression_list:
            self.assertIn(
                expression,
                command_result.stdout.decode(),
            )
        self.assertTrue(
            re.search(
                """{\n    "LogicalResourceId": "ServerlessRestApiDeployment.*",\n    "PhysicalResourceId": "-"\n  }""",
                command_result.stdout.decode(),
            )
        )

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
        config_file_name = stack_name + ".toml"
        region = boto3.Session().region_name
        deploy_command_list = self.get_deploy_command_list(
            template_file=template_path,
            guided=True,
            config_file=config_file_name,
            region=region,
            confirm_changeset=True,
            disable_rollback=True,
        )
        deploy_process_execute = run_command_with_input(
            deploy_command_list, "{}\n{}\nY\nY\nY\nY\nY\n\n\nY\n".format(stack_name, region).encode()
        )
        cmdlist = self.get_resources_command_list(
            stack_name=stack_name, region=region, output="json", template_file=template_path
        )
        command_result = run_command(cmdlist, cwd=self.working_dir)
        expression_list = [
            """{\n    "LogicalResourceId": "HelloWorldFunction",\n    "PhysicalResourceId": ".*HelloWorldFunction.*"\n  }""",
            """{\n    "LogicalResourceId": "HelloWorldFunctionRole",\n    "PhysicalResourceId": ".*HelloWorldFunctionRole.*"\n  }""",
            """{\n    "LogicalResourceId": "HelloWorldFunctionHelloWorldPermissionProd",\n    "PhysicalResourceId": ".*HelloWorldFunctionHelloWorldPermissionProd.*"\n  }""",
            """{\n    "LogicalResourceId": "ServerlessRestApi",\n    "PhysicalResourceId": ".*"\n  }""",
            """{\n    "LogicalResourceId": "ServerlessRestApiProdStage",\n    "PhysicalResourceId": ".*"\n  }""",
            """{\n    "LogicalResourceId": "ServerlessRestApiDeployment.*",\n    "PhysicalResourceId": ".*"\n  }""",
        ]
        for expression in expression_list:
            self.assertTrue(
                re.search(
                    expression,
                    command_result.stdout.decode(),
                )
            )

    def test_stack_does_not_exist(self):
        template_path = self.list_test_data_path.joinpath("test_stack_creation_template.yaml")
        stack_name = method_to_stack_name(self.id())
        config_file_name = stack_name + ".toml"
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
