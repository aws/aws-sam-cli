import shutil
from pathlib import Path
from subprocess import Popen, PIPE, TimeoutExpired
from typing import Optional
from unittest import skipIf

import docker
import pytest
from docker.errors import APIError
from parameterized import parameterized
from pip._vendor.rich import json

from tests.integration.local.invoke.invoke_integ_base import InvokeIntegBase, TIMEOUT
from tests.testing_utils import CI_OVERRIDE, IS_WINDOWS, RUNNING_ON_CI


class InvokeTerraformApplicationIntegBase(InvokeIntegBase):
    terraform_application: Optional[Path] = None

    @classmethod
    def setUpClass(cls):
        super(InvokeTerraformApplicationIntegBase, cls).setUpClass()
        cls.terraform_application_path = str(cls.test_data_path.joinpath("invoke", cls.terraform_application))

    def run_command(self, command_list, env=None, input=None):
        process = Popen(command_list, stdout=PIPE, stderr=PIPE, stdin=PIPE, env=env, cwd=self.terraform_application_path)
        try:
            (stdout, stderr) = process.communicate(input=input, timeout=TIMEOUT)
            return stdout, stderr, process.returncode
        except TimeoutExpired:
            process.kill()
            raise


class TestInvokeTerraformApplicationWithoutBuild(InvokeTerraformApplicationIntegBase):
    terraform_application = Path("terraform/simple_application_no_building_logic")
    functions = [
        "s3_lambda_function",
        "aws_lambda_function.s3_lambda",
        "root_lambda",
        "aws_lambda_function.root_lambda",
        "level1_lambda_function",
        "module.level1_lambda.aws_lambda_function.this",
        "level2_lambda_function",
        "module.level1_lambda.module.level2_lambda.aws_lambda_function.this",
    ]

    def tearDown(self) -> None:
        try:
            shutil.rmtree(str(Path(self.terraform_application_path).joinpath(".aws-sam")))  # type: ignore
        except FileNotFoundError:
            pass

    @skipIf(
        not CI_OVERRIDE,
        "Skip Terraform test cases unless running in CI",
    )
    @parameterized.expand(functions)
    @pytest.mark.flaky(reruns=3)
    def test_invoke_function(self, function_name):
        local_invoke_command_list = self.get_command_list(
            function_to_invoke=function_name, hook_package_id="terraform", beta_features=True
        )
        stdout, _, return_code = self.run_command(local_invoke_command_list)

        # Get the response without the sam-cli prompts that proceed it
        response = json.loads(stdout.decode("utf-8").split("\n")[0])
        expected_response = json.loads('{"statusCode":200,"body":"{\\"message\\": \\"hello world\\"}"}')

        self.assertEqual(return_code, 0)
        self.assertEqual(response, expected_response)

    @skipIf(
        not CI_OVERRIDE,
        "Skip Terraform test cases unless running in CI",
    )
    @pytest.mark.flaky(reruns=3)
    def test_invoke_function_get_experimental_prompted(self):
        local_invoke_command_list = self.get_command_list(
            function_to_invoke="s3_lambda_function", hook_package_id="terraform"
        )
        stdout, _, return_code = self.run_command(local_invoke_command_list, input=b'Y\n\n')

        terraform_beta_feature_prompted_text = (
            "Supporting Terraform applications is a beta feature.\n"
            "Please confirm if you would like to proceed using SAM CLI with terraform application.\n"
            "You can also enable this beta feature with 'sam local invoke --beta-features'."
        )
        self.assertRegex(stdout.decode("utf-8"),terraform_beta_feature_prompted_text )
        response = json.loads(stdout.decode("utf-8").split("\n")[2][85:].strip())
        expected_response = json.loads('{"statusCode":200,"body":"{\\"message\\": \\"hello world\\"}"}')

        self.assertEqual(return_code, 0)
        self.assertEqual(response, expected_response)

    @skipIf(
        not CI_OVERRIDE,
        "Skip Terraform test cases unless running in CI",
    )
    @pytest.mark.flaky(reruns=3)
    def test_invoke_function_get_experimental_prompted_input_no(self):
        local_invoke_command_list = self.get_command_list(
            function_to_invoke="s3_lambda_function", hook_package_id="terraform"
        )
        stdout, stderr, return_code = self.run_command(local_invoke_command_list, input=b'N\n\n')

        terraform_beta_feature_prompted_text = (
            "Supporting Terraform applications is a beta feature.\n"
            "Please confirm if you would like to proceed using SAM CLI with terraform application.\n"
            "You can also enable this beta feature with 'sam local invoke --beta-features'."
        )
        self.assertRegex(stdout.decode("utf-8"), terraform_beta_feature_prompted_text)

        process_stderr = stderr.strip()
        self.assertRegex(
            process_stderr.decode("utf-8"),
            "Terraform Support beta feature is not enabled.",
        )

        self.assertEqual(return_code, 0)

    def test_invalid_hook_package_id(self):
        local_invoke_command_list = self.get_command_list("func", hook_package_id="tf")
        _, stderr, return_code = self.run_command(local_invoke_command_list)

        process_stderr = stderr.strip()
        self.assertRegex(
            process_stderr.decode("utf-8"),
            "Error: Invalid value: tf is not a valid hook package id.",
        )
        self.assertNotEqual(return_code, 0)

    def test_invoke_terraform_with_no_beta_feature_option(self):
        local_invoke_command_list = self.get_command_list(
            function_to_invoke="func", hook_package_id="terraform", beta_features=False
        )
        _, stderr, return_code = self.run_command(local_invoke_command_list)

        process_stderr = stderr.strip()
        self.assertRegex(
            process_stderr.decode("utf-8"),
            "Terraform Support beta feature is not enabled.",
        )
        self.assertEqual(return_code, 0)

    def test_invalid_coexist_parameters(self):
        local_invoke_command_list = self.get_command_list(
            "func", hook_package_id="terraform", template_path="template.yaml"
        )
        _, stderr, return_code = self.run_command(local_invoke_command_list)

        process_stderr = stderr.strip()
        self.assertRegex(
            process_stderr.decode("utf-8"),
            "Error: Invalid value: Parameters hook-package-id, and t,template-file,template,parameter-overrides can "
            "not be used together",
        )
        self.assertNotEqual(return_code, 0)


@skipIf(
    ((IS_WINDOWS and RUNNING_ON_CI) and not CI_OVERRIDE),
    "Skip local invoke terraform application tests on windows when running in CI unless overridden",
)
class TestInvokeTerraformApplicationWithLocalImageUri(InvokeTerraformApplicationIntegBase):
    terraform_application = Path("terraform/image_lambda_function_local_image_uri")
    functions = [
        "image_lambda_function",
        "aws_lambda_function.image_lambda",
    ]

    @classmethod
    def setUpClass(cls):
        super(TestInvokeTerraformApplicationWithLocalImageUri, cls).setUpClass()
        cls.client = docker.from_env()
        cls.image_name = "sam-test-lambdaimage"
        cls.docker_tag = f"{cls.image_name}:v1"
        cls.test_data_invoke_path = str(Path(__file__).resolve().parents[2].joinpath("testdata", "invoke"))
        # Directly build an image that will be used across all local invokes in this class.
        for log in cls.client.api.build(
            path=cls.test_data_invoke_path, dockerfile="Dockerfile", tag=cls.docker_tag, decode=True
        ):
            print(log)

    @classmethod
    def tearDownClass(cls):
        try:
            cls.client.api.remove_image(cls.docker_tag)
        except APIError:
            pass

    @parameterized.expand(functions)
    @pytest.mark.flaky(reruns=3)
    def test_invoke_image_function(self, function_name):
        local_invoke_command_list = self.get_command_list(
            function_to_invoke=function_name,
            hook_package_id="terraform",
            event_path=self.event_path,
            beta_features=True,
        )
        stdout, _, return_code = self.run_command(local_invoke_command_list)

        # Get the response without the sam-cli prompts that proceed it
        self.assertEqual(return_code, 0)
        process_stdout = stdout.strip()
        self.assertEqual(process_stdout.decode("utf-8"), '"Hello world"')
