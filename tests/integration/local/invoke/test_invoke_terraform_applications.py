import shutil
from pathlib import Path
from subprocess import Popen, PIPE, TimeoutExpired
from typing import Optional
from unittest import skipIf

import pytest
from parameterized import parameterized
from pip._vendor.rich import json

from tests.integration.local.invoke.invoke_integ_base import InvokeIntegBase, TIMEOUT
from tests.testing_utils import CI_OVERRIDE


class InvokeTerraformApplicationIntegBase(InvokeIntegBase):
    terraform_application: Optional[Path] = None

    @classmethod
    def setUpClass(cls):
        super(InvokeTerraformApplicationIntegBase, cls).setUpClass()
        cls.terraform_application_path = str(cls.test_data_path.joinpath("invoke", cls.terraform_application))

    def run_command(self, command_list, env=None):
        process = Popen(command_list, stdout=PIPE, stderr=PIPE, env=env, cwd=self.terraform_application_path)
        try:
            (stdout, stderr) = process.communicate(timeout=TIMEOUT)
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
        local_invoke_command_list = self.get_command_list(function_to_invoke=function_name, hook_package_id="terraform")
        stdout, _, return_code = self.run_command(local_invoke_command_list)

        # Get the response without the sam-cli prompts that proceed it
        response = json.loads(stdout.decode("utf-8").split("\n")[0])
        expected_response = json.loads('{"statusCode":200,"body":"{\\"message\\": \\"hello world\\"}"}')

        self.assertEqual(return_code, 0)
        self.assertEqual(response, expected_response)

    def test_invalid_hook_package_id(self):
        local_invoke_command_list = self.get_command_list("func", hook_package_id="tf")
        _, stderr, return_code = self.run_command(local_invoke_command_list)

        process_stderr = stderr.strip()
        self.assertRegex(
            process_stderr.decode("utf-8"),
            "Error: Invalid value: tf is not a valid hook package id.",
        )
        self.assertNotEqual(return_code, 0)

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
