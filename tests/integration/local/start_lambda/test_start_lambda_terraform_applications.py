import json
import os
import shutil
import time
import uuid
from pathlib import Path
from subprocess import Popen, PIPE, TimeoutExpired
from typing import Optional, Dict
from unittest import skipIf

import logging

import boto3
from botocore import UNSIGNED
from botocore.config import Config
import docker
import pytest
from docker.errors import APIError
from parameterized import parameterized, parameterized_class

from samcli.commands._utils.experimental import EXPERIMENTAL_WARNING
from samcli.lib.utils.colors import Colored
from tests.integration.local.common_utils import random_port
from tests.integration.local.invoke.layer_utils import LayerUtils
from tests.integration.local.start_lambda.start_lambda_api_integ_base import StartLambdaIntegBaseClass
from tests.testing_utils import CI_OVERRIDE, IS_WINDOWS, RUNNING_ON_CI, RUN_BY_CANARY

LOG = logging.getLogger(__name__)
S3_SLEEP = 3


class StartLambdaTerraformApplicationIntegBase(StartLambdaIntegBaseClass):
    terraform_application: Optional[str] = None
    input: Optional[bytes] = None
    env: Optional[Dict] = None

    @classmethod
    def setUpClass(cls):
        # This is the directory for tests/integration which will be used to file the testdata
        # files for integ tests
        if cls.template_path:
            cls.template = cls.integration_dir + cls.template_path

        if cls.terraform_application:
            cls.working_dir = cls.integration_dir + cls.terraform_application

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

        cls.start_lambda_with_retry(input=cls.input, env=cls.env)

    @classmethod
    def _run_command(cls, command_list, env=None, tf_application=None):
        process = Popen(command_list, stdout=PIPE, stderr=PIPE, env=env, cwd=tf_application)
        try:
            (stdout, stderr) = process.communicate(timeout=300)
            return stdout, stderr, process.returncode
        except TimeoutExpired:
            process.kill()
            raise


class TestLocalStartLambdaTerraformApplicationWithoutBuild(StartLambdaTerraformApplicationIntegBase):
    terraform_application = "/testdata/invoke/terraform/simple_application_no_building_logic"
    template_path = None
    hook_name = "terraform"
    beta_features = True

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


@skipIf(
    (not RUN_BY_CANARY and not CI_OVERRIDE),
    "Skip Terraform test cases unless running in CI",
)
@parameterized_class(
    ("should_apply_first",),
    [
        (False,),
        (True,),
    ],
)
class TestLocalStartLambdaTerraformApplicationWithLayersWithoutBuild(StartLambdaTerraformApplicationIntegBase):
    terraform_application = "/testdata/invoke/terraform/simple_application_with_layers_no_building_logic"
    pre_create_lambda_layers = ["simple_layer1", "simple_layer2", "simple_layer3", "simple_layer33", "simple_layer44"]
    template_path = None
    hook_name = "terraform"
    beta_features = True

    @classmethod
    def setUpClass(cls):
        cls.region_name = os.environ.get("AWS_DEFAULT_REGION", "us-east-1")

        # create some Lambda Layers to be used in the Terraform project
        working_dir = cls.integration_dir + cls.terraform_application
        cls.layerUtils = LayerUtils(cls.region_name, str(Path(working_dir).joinpath("artifacts")))
        cls.layer_postfix = str(uuid.uuid4())

        for lambda_layer_name in cls.pre_create_lambda_layers:
            cls.layerUtils.upsert_layer(
                f"{lambda_layer_name}-{cls.layer_postfix}",
                f"{lambda_layer_name}-{cls.layer_postfix}",
                f"{lambda_layer_name}.zip",
            )

        # create override file in const_layer module to test using the module default provided value
        const_layer_module_input_layer_overwrite = str(
            Path(working_dir).joinpath("const_layer", "variable_name_override.tf")
        )
        _2nd_layer_arn = cls.layerUtils.parameters_overrides[f"{cls.pre_create_lambda_layers[1]}-{cls.layer_postfix}"]
        lines = [
            bytes('variable "INPUT_LAYER" {' + os.linesep, "utf-8"),
            bytes("   type = string" + os.linesep, "utf-8"),
            bytes(f'   default="{_2nd_layer_arn}"' + os.linesep, "utf-8"),
            bytes("}", "utf-8"),
        ]
        with open(const_layer_module_input_layer_overwrite, "wb") as file:
            file.writelines(lines)

        # create override file in lambda_function_with_const_layer module to test using the function with constant
        # layers list
        function_with_const_layer_module_function_definition_overwrite = str(
            Path(working_dir).joinpath("lambda_function_with_const_layer", "function_override.tf")
        )
        _4th_layer_arn = cls.layerUtils.parameters_overrides[f"{cls.pre_create_lambda_layers[3]}-{cls.layer_postfix}"]

        function_lines = [
            bytes('resource "aws_lambda_function" "this" {' + os.linesep, "utf-8"),
            bytes("   filename = var.source_code" + os.linesep, "utf-8"),
            bytes('   handler = "app.lambda_handler"' + os.linesep, "utf-8"),
            bytes('   runtime = "python3.8"' + os.linesep, "utf-8"),
            bytes("   function_name = var.function_name" + os.linesep, "utf-8"),
            bytes("   role = aws_iam_role.iam_for_lambda.arn" + os.linesep, "utf-8"),
            bytes(f'   layers = ["{_4th_layer_arn}"]' + os.linesep, "utf-8"),
            bytes("}", "utf-8"),
        ]
        with open(function_with_const_layer_module_function_definition_overwrite, "wb") as file:
            file.writelines(function_lines)

        # create Functions code bucket
        cls.bucket_name = str(uuid.uuid4())

        s3 = boto3.resource("s3")
        cls.s3_bucket = s3.Bucket(cls.bucket_name)
        cls.s3_bucket.create()
        time.sleep(S3_SLEEP)

        # apply the terraform project
        if cls.should_apply_first:
            apply_command = ["terraform", "apply", "-auto-approve", "-input=false"]
            stdout, _, return_code = cls._run_command(command_list=apply_command, env=cls._add_tf_project_variables())
        cls.env = cls._add_tf_project_variables()
        super(TestLocalStartLambdaTerraformApplicationWithLayersWithoutBuild, cls).setUpClass()

    @classmethod
    def _add_tf_project_variables(cls):
        environment_variables = os.environ.copy()
        environment_variables["TF_VAR_INPUT_LAYER"] = cls.layerUtils.parameters_overrides[
            f"{cls.pre_create_lambda_layers[0]}-{cls.layer_postfix}"
        ]
        environment_variables["TF_VAR_LAYER_NAME"] = f"{cls.pre_create_lambda_layers[2]}-{cls.layer_postfix}"
        environment_variables["TF_VAR_LAYER44_NAME"] = f"{cls.pre_create_lambda_layers[4]}-{cls.layer_postfix}"
        environment_variables["TF_VAR_BUCKET_NAME"] = cls.bucket_name
        return environment_variables

    @classmethod
    def tearDownClass(cls):
        """Clean up and delete the lambda layers, and bucket if it is not pre-created"""

        # delete the created terraform project
        if cls.should_apply_first:
            apply_command = ["terraform", "destroy", "-auto-approve", "-input=false"]
            stdout, _, return_code = cls._run_command(command_list=apply_command, env=cls._add_tf_project_variables())

        # delete the created layers
        cls.layerUtils.delete_layers()

        # delete the override file
        try:
            os.remove(str(Path(cls.working_dir).joinpath("const_layer", "variable_name_override.tf")))
            os.remove(str(Path(cls.working_dir).joinpath("lambda_function_with_const_layer", "function_override.tf")))
            shutil.rmtree(str(Path(cls.working_dir).joinpath(".aws-sam-iacs")))
            shutil.rmtree(str(Path(cls.working_dir).joinpath(".terraform")))
            os.remove(str(Path(cls.working_dir).joinpath(".terraform.lock.hcl")))
        except (FileNotFoundError, PermissionError):
            pass

        # delete the function code bucket
        cls.s3_bucket.objects.all().delete()
        time.sleep(S3_SLEEP)
        cls.s3_bucket.delete()

        super(TestLocalStartLambdaTerraformApplicationWithLayersWithoutBuild, cls).tearDownClass()

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
        ("module.function44.aws_lambda_function.this", "hello world 44"),
        ("module.function33.aws_lambda_function.this", "hello world 33"),
        ("module.function8.aws_lambda_function.this[0]", "hello world 8"),
        ("module.function9.aws_lambda_function.this[0]", "hello world 9"),
        ("aws_lambda_function.function1", "hello world 1"),
        ("aws_lambda_function.function2", "hello world 2"),
        ("aws_lambda_function.function3", "hello world 3"),
        ("aws_lambda_function.function4", "hello world 4"),
        ("module.function5[0].aws_lambda_function.this[0]", "hello world 5"),
        ("aws_lambda_function.function6", "hello world 6"),
        ("aws_lambda_function.function7", "hello world 7"),
    ]

    @parameterized.expand(functions)
    @pytest.mark.flaky(reruns=3)
    def test_invoke_function(self, function_name, expected_output):
        response = self.lambda_client.invoke(FunctionName=function_name)

        response_body = json.loads(response.get("Payload").read().decode("utf-8"))
        expected_response = json.loads('{"statusCode":200,"body":"{\\"message\\": \\"' + expected_output + '\\"}"}')

        self.assertEqual(response_body, expected_response)
        self.assertEqual(response.get("StatusCode"), 200)


@skipIf(
    (not RUN_BY_CANARY and not CI_OVERRIDE),
    "Skip Terraform test cases unless running in CI",
)
class TestInvalidTerraformApplicationThatReferToS3BucketNotCreatedYet(StartLambdaTerraformApplicationIntegBase):
    terraform_application = "/testdata/invoke/terraform/invalid_no_local_code_project"
    template_path = None
    hook_name = "terraform"
    beta_features = True

    @classmethod
    def setUpClass(cls):
        # over write the parent setup
        pass

    @classmethod
    def tearDownClass(cls):
        # over write the parent tear down
        pass

    def setUp(self):
        self.working_dir = self.integration_dir + self.terraform_application
        self.port = str(random_port())

        # remove all containers if there
        self.docker_client = docker.from_env()
        for container in self.docker_client.api.containers():
            try:
                self.docker_client.api.remove_container(container, force=True)
            except APIError as ex:
                LOG.error("Failed to remove container %s", container, exc_info=ex)

    def tearDown(self):
        # delete the override file
        try:
            shutil.rmtree(str(Path(self.working_dir).joinpath(".aws-sam-iacs")))
            shutil.rmtree(str(Path(self.working_dir).joinpath(".terraform")))
            os.remove(str(Path(self.working_dir).joinpath(".terraform.lock.hcl")))
        except (FileNotFoundError, PermissionError):
            pass

    @pytest.mark.flaky(reruns=3)
    def test_invoke_function(self):
        command_list = self.get_start_lambda_command(
            port=self.port,
            hook_name=self.hook_name,
            beta_features=self.beta_features,
        )
        _, stderr, return_code = self._run_command(command_list, tf_application=self.working_dir)

        process_stderr = stderr.strip()
        self.assertRegex(
            process_stderr.decode("utf-8"),
            "Error: Lambda resource aws_lambda_function.function is referring to an S3 bucket that is not created yet, "
            "and there is no sam metadata resource set for it to build its code locally",
        )
        self.assertNotEqual(return_code, 0)


@skipIf(
    (not RUN_BY_CANARY and not CI_OVERRIDE),
    "Skip Terraform test cases unless running in CI",
)
class TestLocalStartLambdaTerraformApplicationWithExperimentalPromptYes(StartLambdaTerraformApplicationIntegBase):
    terraform_application = "/testdata/invoke/terraform/simple_application_no_building_logic"
    template_path = None
    hook_name = "terraform"
    input = b"Y\n"
    collect_start_lambda_process_output = True

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

    @pytest.mark.flaky(reruns=3)
    def test_invoke_function(self):
        response = self.lambda_client.invoke(FunctionName="s3_lambda_function")

        response_body = json.loads(response.get("Payload").read().decode("utf-8"))
        expected_response = json.loads('{"statusCode":200,"body":"{\\"message\\": \\"hello world\\"}"}')

        self.assertEqual(response_body, expected_response)
        self.assertEqual(response.get("StatusCode"), 200)


@skipIf(
    (not RUN_BY_CANARY and not CI_OVERRIDE),
    "Skip Terraform test cases unless running in CI",
)
class TestLocalStartLambdaTerraformApplicationWithBetaFeatures(StartLambdaTerraformApplicationIntegBase):
    terraform_application = "/testdata/invoke/terraform/simple_application_no_building_logic"
    template_path = None
    hook_name = "terraform"
    beta_features = True
    collect_start_lambda_process_output = True

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

    @pytest.mark.flaky(reruns=3)
    def test_invoke_function_and_warning_message_is_printed(self):
        self.assertIn(Colored().yellow(EXPERIMENTAL_WARNING), self.start_lambda_process_error)


class TestLocalStartLambdaTerraformApplicationWithExperimentalPromptNo(StartLambdaTerraformApplicationIntegBase):
    terraform_application = "/testdata/invoke/terraform/simple_application_no_building_logic"
    template_path = None
    hook_name = "terraform"
    input = b"N\n"
    collect_start_lambda_process_output = True

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

    @skipIf(
        not CI_OVERRIDE,
        "Skip Terraform test cases unless running in CI",
    )
    @pytest.mark.flaky(reruns=3)
    def test_invoke_function(self):
        self.assertRegex(
            self.start_lambda_process_error,
            "Terraform Support beta feature is not enabled.",
        )


class TestLocalStartLambdaInvalidUsecasesTerraform(StartLambdaTerraformApplicationIntegBase):
    @classmethod
    def setUpClass(cls):
        # As we test the invalid scenarios in this class, so we do not expect that sam local lambda command will work
        # fine, and so we do not need to setup any port or any other setup.
        pass

    @classmethod
    def tearDownClass(cls):
        # As we test the invalid scenarios in this class, so we do not expect that sam local lambda command will work
        # fine, and so we do any process to kill, or docker image to clean.
        pass

    def setUp(self):
        self.integration_dir = str(Path(__file__).resolve().parents[2])
        terraform_application = "/testdata/invoke/terraform/simple_application_no_building_logic"
        self.working_dir = self.integration_dir + terraform_application

    def test_invalid_hook_name(self):
        command_list = self.get_start_lambda_command(hook_name="tf")
        _, stderr, return_code = self._run_command(command_list, tf_application=self.working_dir)

        process_stderr = stderr.strip()
        self.assertRegex(
            process_stderr.decode("utf-8"),
            "Error: Invalid value: tf is not a valid hook name.",
        )
        self.assertNotEqual(return_code, 0)

    def test_start_lambda_with_no_beta_feature(self):
        command_list = self.get_start_lambda_command(hook_name="terraform", beta_features=False)

        _, stderr, return_code = self._run_command(command_list, tf_application=self.working_dir)

        process_stderr = stderr.strip()
        self.assertRegex(
            process_stderr.decode("utf-8"),
            "Terraform Support beta feature is not enabled.",
        )
        self.assertEqual(return_code, 0)

    def test_start_lambda_with_no_beta_feature_option_in_samconfig_toml(self):
        samconfig_toml_path = Path(self.working_dir).joinpath("samconfig.toml")
        samconfig_lines = [
            bytes("version = 0.1" + os.linesep, "utf-8"),
            bytes("[default.global.parameters]" + os.linesep, "utf-8"),
            bytes("beta_features = false" + os.linesep, "utf-8"),
        ]
        with open(samconfig_toml_path, "wb") as file:
            file.writelines(samconfig_lines)

        command_list = self.get_start_lambda_command(hook_name="terraform")

        _, stderr, return_code = self._run_command(command_list, tf_application=self.working_dir)

        process_stderr = stderr.strip()
        self.assertRegex(
            process_stderr.decode("utf-8"),
            "Terraform Support beta feature is not enabled.",
        )
        self.assertEqual(return_code, 0)
        # delete the samconfig file
        try:
            os.remove(samconfig_toml_path)
        except (FileNotFoundError, PermissionError):
            pass

    def test_start_lambda_with_no_beta_feature_option_in_environment_variables(self):
        environment_variables = os.environ.copy()
        environment_variables["SAM_CLI_BETA_TERRAFORM_SUPPORT"] = "False"

        command_list = self.get_start_lambda_command(hook_name="terraform")
        _, stderr, return_code = self._run_command(
            command_list, tf_application=self.working_dir, env=environment_variables
        )

        process_stderr = stderr.strip()
        self.assertRegex(
            process_stderr.decode("utf-8"),
            "Terraform Support beta feature is not enabled.",
        )
        self.assertEqual(return_code, 0)

    def test_invalid_coexist_parameters(self):

        command_list = self.get_start_lambda_command(hook_name="terraform", template_path="path/template.yaml")
        _, stderr, return_code = self._run_command(command_list, tf_application=self.working_dir)

        process_stderr = stderr.strip()
        self.assertRegex(
            process_stderr.decode("utf-8"),
            "Error: Invalid value: Parameters hook-name, and t,template-file,template,parameter-overrides cannot "
            "be used together",
        )
        self.assertNotEqual(return_code, 0)


@skipIf(
    ((not RUN_BY_CANARY) or (IS_WINDOWS and RUNNING_ON_CI) and not CI_OVERRIDE),
    "Skip local start-lambda terraform applications tests on windows when running in CI unless overridden",
)
class TestLocalStartLambdaTerraformApplicationWithLocalImageUri(StartLambdaTerraformApplicationIntegBase):
    terraform_application = "/testdata/invoke/terraform/image_lambda_function_local_image_uri"
    template_path = None
    hook_name = "terraform"
    beta_features = True
    functions = [
        "module.image_lambda2.aws_lambda_function.this[0]",
        "image_lambda2",
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

        cls.env_var_path = cls.integration_dir + "/testdata/invoke/vars.json"

        if cls.build_before_invoke:
            cls.build()

        cls.docker_client = docker.from_env()
        cls.image_name = "sam-test-lambdaimage"
        cls.docker_tag = f"{cls.image_name}:v1"
        cls.test_data_invoke_path = str(Path(__file__).resolve().parents[2].joinpath("testdata", "invoke"))
        # Directly build an image that will be used across all local invokes in this class.
        for log in cls.docker_client.api.build(
            path=cls.test_data_invoke_path, dockerfile="Dockerfile", tag=cls.docker_tag, decode=True
        ):
            print(log)

        cls.start_lambda_with_retry()

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
