import json
import os
from pathlib import Path
from subprocess import Popen, PIPE, TimeoutExpired
from typing import Optional
from unittest import skipIf, TestCase

import logging

import boto3
from botocore import UNSIGNED
from botocore.config import Config
import docker
import pytest
from docker.errors import APIError
from parameterized import parameterized

from tests.integration.local.start_lambda.start_lambda_api_integ_base import StartLambdaIntegBaseClass
from tests.testing_utils import CI_OVERRIDE, IS_WINDOWS, RUNNING_ON_CI

LOG = logging.getLogger(__name__)


class StartLambdaTerraformApplicationIntegBase(StartLambdaIntegBaseClass):
    terraform_application: Optional[str] = None

    @classmethod
    def setUpClass(cls):
        # This is the directory for tests/integration which will be used to file the testdata
        # files for integ tests
        if cls.template_path:
            cls.template = cls.integration_dir + cls.template_path

        if cls.terraform_application:
            cls.working_dir = cls.integration_dir + cls.terraform_application

        cls.port = str(StartLambdaIntegBaseClass.random_port())
        cls.env_var_path = cls.integration_dir + "/testdata/invoke/vars.json"

        if cls.build_before_invoke:
            cls.build()

        # remove all containers if there
        cls.docker_client = docker.from_env()
        for container in cls.docker_client.api.containers():
            try:
                cls.docker_client.api.remove_container(container, force=True)
            except APIError as ex:
                LOG.error("Failed to remove container %s", container, exc_info=ex)

        cls.start_lambda()


class TestLocalStartLambdaTerraformApplicationWithoutBuild(StartLambdaTerraformApplicationIntegBase):
    terraform_application = "/testdata/invoke/terraform/simple_application_no_building_logic"
    template_path = None
    hook_package_id = "terraform"

    def setUp(self):
        self.url = "http://127.0.0.1:{}".format(self.port)
        self.lambda_client = boto3.client(
            "lambda",
            endpoint_url=self.url,
            region_name="us-east-1",
            use_ssl=False,
            verify=False,
            config=Config(signature_version=UNSIGNED, read_timeout=120, retries={"max_attempts": 0}),
        )

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

    @skipIf(
        not CI_OVERRIDE,
        "Skip Terraform test cases unless running in CI",
    )
    @parameterized.expand(functions)
    @pytest.mark.flaky(reruns=3)
    def test_invoke_function(self, function_name):
        response = self.lambda_client.invoke(FunctionName=function_name)

        response_body = json.loads(response.get("Payload").read().decode("utf-8"))
        expected_response = json.loads('{"statusCode":200,"body":"{\\"message\\": \\"hello world\\"}"}')

        self.assertEqual(response_body, expected_response)
        self.assertEqual(response.get("StatusCode"), 200)


class TestLocalStartLambdaInvalidUsecasesTerraform(TestCase):
    def setUp(self):
        self.integration_dir = str(Path(__file__).resolve().parents[2])
        terraform_application = "/testdata/invoke/terraform/simple_application_no_building_logic"
        self.terraform_application_path = self.integration_dir + terraform_application

    def test_invalid_hook_package_id(self):
        command = "sam"
        if os.getenv("SAM_CLI_DEV"):
            command = "samdev"

        command_list = [command, "local", "start-lambda", "--hook-package-id", "tf"]

        _, stderr, return_code = self._run_command(command_list, tf_application=self.terraform_application_path)

        process_stderr = stderr.strip()
        self.assertRegex(
            process_stderr.decode("utf-8"),
            "Error: Invalid value: tf is not a valid hook package id.",
        )
        self.assertNotEqual(return_code, 0)

    def test_invalid_coexist_parameters(self):
        command = "sam"
        if os.getenv("SAM_CLI_DEV"):
            command = "samdev"

        command_list = [command, "local", "start-lambda", "--hook-package-id", "terraform", "-t", "path/template.yaml"]

        _, stderr, return_code = self._run_command(command_list, tf_application=self.terraform_application_path)

        process_stderr = stderr.strip()
        self.assertRegex(
            process_stderr.decode("utf-8"),
            "Error: Invalid value: Parameters hook-package-id, and t,template-file,template,parameter-overrides can "
            "not be used together",
        )
        self.assertNotEqual(return_code, 0)

    def _run_command(self, command_list, env=None, tf_application=None):
        process = Popen(command_list, stdout=PIPE, stderr=PIPE, env=env, cwd=tf_application)
        try:
            (stdout, stderr) = process.communicate(timeout=5)
            return stdout, stderr, process.returncode
        except TimeoutExpired:
            process.kill()
            raise


@skipIf(
    ((IS_WINDOWS and RUNNING_ON_CI) and not CI_OVERRIDE),
    "Skip local start-lambda terraform applications tests on windows when running in CI unless overridden",
)
class TestLocalStartLambdaTerraformApplicationWithLocalImageUri(StartLambdaTerraformApplicationIntegBase):
    terraform_application = "/testdata/invoke/terraform/image_lambda_function_local_image_uri"
    template_path = None
    hook_package_id = "terraform"
    functions = [
        "image_lambda_function",
        "aws_lambda_function.image_lambda",
    ]

    def setUp(self):
        self.url = "http://127.0.0.1:{}".format(self.port)
        self.lambda_client = boto3.client(
            "lambda",
            endpoint_url=self.url,
            region_name="us-east-1",
            use_ssl=False,
            verify=False,
            config=Config(signature_version=UNSIGNED, read_timeout=120, retries={"max_attempts": 0}),
        )

    @classmethod
    def setUpClass(cls):
        if cls.template_path:
            cls.template = cls.integration_dir + cls.template_path

        if cls.terraform_application:
            cls.working_dir = cls.integration_dir + cls.terraform_application

        cls.port = str(StartLambdaIntegBaseClass.random_port())
        cls.env_var_path = cls.integration_dir + "/testdata/invoke/vars.json"

        if cls.build_before_invoke:
            cls.build()

        # remove all containers if there
        cls.docker_client = docker.from_env()
        for container in cls.docker_client.api.containers():
            try:
                cls.docker_client.api.remove_container(container, force=True)
            except APIError as ex:
                LOG.error("Failed to remove container %s", container, exc_info=ex)

        cls.image_name = "sam-test-lambdaimage"
        cls.docker_tag = f"{cls.image_name}:v1"
        cls.test_data_invoke_path = str(Path(__file__).resolve().parents[2].joinpath("testdata", "invoke"))
        # Directly build an image that will be used across all local invokes in this class.
        for log in cls.docker_client.api.build(
            path=cls.test_data_invoke_path, dockerfile="Dockerfile", tag=cls.docker_tag, decode=True
        ):
            print(log)

        cls.start_lambda()

    @classmethod
    def tearDownClass(cls):
        try:
            cls.docker_client.api.remove_image(cls.docker_tag)
        except APIError:
            pass

    @parameterized.expand(functions)
    @pytest.mark.flaky(reruns=3)
    def test_start_lambda_image_function(self, function_name):
        response = self.lambda_client.invoke(
            FunctionName=function_name, Payload='{"key1": "value1","key2": "value2","key3": "value3"}'
        )

        response_body = json.loads(response.get("Payload").read().decode("utf-8"))

        self.assertEqual(response_body, "Hello world")
        self.assertEqual(response.get("StatusCode"), 200)
