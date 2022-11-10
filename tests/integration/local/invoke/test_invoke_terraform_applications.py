import json
import os
import logging
import shutil
import time
import uuid
from pathlib import Path
from subprocess import Popen, PIPE, TimeoutExpired
from typing import Optional
from unittest import skipIf

import boto3
import docker
import pytest
from docker.errors import APIError
from parameterized import parameterized, parameterized_class

from samcli.commands._utils.experimental import EXPERIMENTAL_WARNING
from samcli.lib.utils.colors import Colored
from tests.integration.local.invoke.invoke_integ_base import InvokeIntegBase, TIMEOUT
from tests.integration.local.invoke.layer_utils import LayerUtils
from tests.integration.local.start_lambda.start_lambda_api_integ_base import StartLambdaIntegBaseClass
from tests.testing_utils import CI_OVERRIDE, IS_WINDOWS, RUNNING_ON_CI, RUN_BY_CANARY

LOG = logging.getLogger(__name__)
S3_SLEEP = 3


class InvokeTerraformApplicationIntegBase(InvokeIntegBase):
    terraform_application: Optional[Path] = None

    @classmethod
    def setUpClass(cls):
        super(InvokeTerraformApplicationIntegBase, cls).setUpClass()
        cls.terraform_application_path = str(cls.test_data_path.joinpath("invoke", cls.terraform_application))

    @classmethod
    def run_command(cls, command_list, env=None, input=None):
        process = Popen(command_list, stdout=PIPE, stderr=PIPE, stdin=PIPE, env=env, cwd=cls.terraform_application_path)
        try:
            (stdout, stderr) = process.communicate(input=input, timeout=TIMEOUT)
            LOG.info("sam stdout: %s", stdout.decode("utf-8"))
            LOG.info("sam stderr: %s", stderr.decode("utf-8"))
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
            shutil.rmtree(str(Path(self.terraform_application_path).joinpath(".aws-sam-iacs")))  # type: ignore
            shutil.rmtree(str(Path(self.terraform_application_path).joinpath(".terraform")))  # type: ignore
            os.remove(str(Path(self.terraform_application_path).joinpath(".terraform.lock.hcl")))  # type: ignore
        except (FileNotFoundError, PermissionError):
            pass

    @skipIf(
        not CI_OVERRIDE,
        "Skip Terraform test cases unless running in CI",
    )
    @parameterized.expand(functions)
    @pytest.mark.flaky(reruns=3)
    def test_invoke_function(self, function_name):
        local_invoke_command_list = self.get_command_list(
            function_to_invoke=function_name, hook_name="terraform", beta_features=True
        )
        stdout, _, return_code = self.run_command(local_invoke_command_list)

        # Get the response without the sam-cli prompts that proceed it
        response = json.loads(stdout.decode("utf-8").split("\n")[-1])
        expected_response = json.loads('{"statusCode":200,"body":"{\\"message\\": \\"hello world\\"}"}')

        self.assertEqual(return_code, 0)
        self.assertEqual(response, expected_response)

    @skipIf(
        not CI_OVERRIDE,
        "Skip Terraform test cases unless running in CI",
    )
    @parameterized.expand(functions)
    @pytest.mark.flaky(reruns=3)
    def test_invoke_terraform_with_beta_feature_option_in_samconfig_toml(self, function_name):
        samconfig_toml_path = Path(self.terraform_application_path).joinpath("samconfig.toml")
        samconfig_lines = [
            bytes("version = 0.1" + os.linesep, "utf-8"),
            bytes("[default.global.parameters]" + os.linesep, "utf-8"),
            bytes("beta_features = true" + os.linesep, "utf-8"),
        ]
        with open(samconfig_toml_path, "wb") as file:
            file.writelines(samconfig_lines)

        local_invoke_command_list = self.get_command_list(function_to_invoke=function_name, hook_name="terraform")
        stdout, _, return_code = self.run_command(local_invoke_command_list)

        # Get the response without the sam-cli prompts that proceed it
        response = json.loads(stdout.decode("utf-8").split("\n")[-1])
        expected_response = json.loads('{"statusCode":200,"body":"{\\"message\\": \\"hello world\\"}"}')

        self.assertEqual(return_code, 0)
        self.assertEqual(response, expected_response)
        # delete the samconfig file
        try:
            os.remove(samconfig_toml_path)
        except FileNotFoundError:
            pass

    @skipIf(
        not CI_OVERRIDE,
        "Skip Terraform test cases unless running in CI",
    )
    @parameterized.expand(functions)
    @pytest.mark.flaky(reruns=3)
    def test_invoke_terraform_with_beta_feature_option_as_environment_variable(self, function_name):
        environment_variables = os.environ.copy()
        environment_variables["SAM_CLI_BETA_TERRAFORM_SUPPORT"] = "1"

        local_invoke_command_list = self.get_command_list(function_to_invoke=function_name, hook_name="terraform")
        stdout, _, return_code = self.run_command(local_invoke_command_list, env=environment_variables)

        # Get the response without the sam-cli prompts that proceed it
        response = json.loads(stdout.decode("utf-8").split("\n")[-1])
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
            function_to_invoke="s3_lambda_function", hook_name="terraform"
        )
        stdout, stderr, return_code = self.run_command(local_invoke_command_list, input=b"Y\n\n")

        terraform_beta_feature_prompted_text = (
            "Supporting Terraform applications is a beta feature.\n"
            "Please confirm if you would like to proceed using AWS SAM CLI with terraform application.\n"
            "You can also enable this beta feature with 'sam local invoke --beta-features'."
        )
        self.assertRegex(stdout.decode("utf-8"), terraform_beta_feature_prompted_text)
        self.assertTrue(stderr.decode("utf-8").startswith(Colored().yellow(EXPERIMENTAL_WARNING)))

        response = json.loads(stdout.decode("utf-8").split("\n")[2][85:].strip())
        expected_response = json.loads('{"statusCode":200,"body":"{\\"message\\": \\"hello world\\"}"}')

        self.assertEqual(return_code, 0)
        self.assertEqual(response, expected_response)

    @skipIf(
        not CI_OVERRIDE,
        "Skip Terraform test cases unless running in CI",
    )
    @pytest.mark.flaky(reruns=3)
    def test_invoke_function_with_beta_feature_expect_warning_message(self):
        local_invoke_command_list = self.get_command_list(
            function_to_invoke="s3_lambda_function", hook_name="terraform", beta_features=True
        )
        stdout, stderr, return_code = self.run_command(local_invoke_command_list)

        terraform_beta_feature_prompted_text = (
            "Supporting Terraform applications is a beta feature.\n"
            "Please confirm if you would like to proceed using AWS SAM CLI with terraform application.\n"
            "You can also enable this beta feature with 'sam local invoke --beta-features'."
        )
        self.assertNotRegex(stdout.decode("utf-8"), terraform_beta_feature_prompted_text)
        self.assertTrue(stderr.decode("utf-8").startswith(Colored().yellow(EXPERIMENTAL_WARNING)))

        response = json.loads(stdout.decode("utf-8").split("\n")[-1])
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
            function_to_invoke="s3_lambda_function", hook_name="terraform"
        )
        stdout, stderr, return_code = self.run_command(local_invoke_command_list, input=b"N\n\n")

        terraform_beta_feature_prompted_text = (
            "Supporting Terraform applications is a beta feature.\n"
            "Please confirm if you would like to proceed using AWS SAM CLI with terraform application.\n"
            "You can also enable this beta feature with 'sam local invoke --beta-features'."
        )
        self.assertRegex(stdout.decode("utf-8"), terraform_beta_feature_prompted_text)

        process_stderr = stderr.strip()
        self.assertRegex(
            process_stderr.decode("utf-8"),
            "Terraform Support beta feature is not enabled.",
        )

        self.assertEqual(return_code, 0)

    def test_invalid_hook_name(self):
        local_invoke_command_list = self.get_command_list("func", hook_name="tf")
        _, stderr, return_code = self.run_command(local_invoke_command_list)

        process_stderr = stderr.strip()
        self.assertRegex(
            process_stderr.decode("utf-8"),
            "Error: Invalid value: tf is not a valid hook name.",
        )
        self.assertNotEqual(return_code, 0)

    def test_invoke_terraform_with_no_beta_feature_option(self):
        local_invoke_command_list = self.get_command_list(
            function_to_invoke="func", hook_name="terraform", beta_features=False
        )
        _, stderr, return_code = self.run_command(local_invoke_command_list)

        process_stderr = stderr.strip()
        self.assertRegex(
            process_stderr.decode("utf-8"),
            "Terraform Support beta feature is not enabled.",
        )
        self.assertEqual(return_code, 0)

    def test_invoke_terraform_with_no_beta_feature_option_in_samconfig_toml(self):
        samconfig_toml_path = Path(self.terraform_application_path).joinpath("samconfig.toml")
        samconfig_lines = [
            bytes("version = 0.1" + os.linesep, "utf-8"),
            bytes("[default.global.parameters]" + os.linesep, "utf-8"),
            bytes("beta_features = false" + os.linesep, "utf-8"),
        ]
        with open(samconfig_toml_path, "wb") as file:
            file.writelines(samconfig_lines)

        local_invoke_command_list = self.get_command_list(function_to_invoke="func", hook_name="terraform")
        _, stderr, return_code = self.run_command(local_invoke_command_list)

        process_stderr = stderr.strip()
        self.assertRegex(
            process_stderr.decode("utf-8"),
            "Terraform Support beta feature is not enabled.",
        )
        self.assertEqual(return_code, 0)
        # delete the samconfig file
        try:
            os.remove(samconfig_toml_path)
        except FileNotFoundError:
            pass

    def test_invoke_terraform_with_no_beta_feature_option_as_environment_variable(self):
        environment_variables = os.environ.copy()
        environment_variables["SAM_CLI_BETA_TERRAFORM_SUPPORT"] = "False"

        local_invoke_command_list = self.get_command_list(function_to_invoke="func", hook_name="terraform")
        _, stderr, return_code = self.run_command(local_invoke_command_list, env=environment_variables)

        process_stderr = stderr.strip()
        self.assertRegex(
            process_stderr.decode("utf-8"),
            "Terraform Support beta feature is not enabled.",
        )
        self.assertEqual(return_code, 0)

    def test_invalid_coexist_parameters(self):
        local_invoke_command_list = self.get_command_list("func", hook_name="terraform", template_path="template.yaml")
        _, stderr, return_code = self.run_command(local_invoke_command_list)

        process_stderr = stderr.strip()
        self.assertRegex(
            process_stderr.decode("utf-8"),
            "Error: Invalid value: Parameters hook-name, and t,template-file,template,parameter-overrides cannot "
            "be used together",
        )
        self.assertNotEqual(return_code, 0)


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
class TestInvokeTerraformApplicationWithLayersWithoutBuild(InvokeTerraformApplicationIntegBase):
    terraform_application = Path("terraform/simple_application_with_layers_no_building_logic")
    pre_create_lambda_layers = ["simple_layer1", "simple_layer2", "simple_layer3", "simple_layer33", "simple_layer44"]
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

    @classmethod
    def setUpClass(cls):
        super(TestInvokeTerraformApplicationWithLayersWithoutBuild, cls).setUpClass()
        cls.region_name = os.environ.get("AWS_DEFAULT_REGION", "us-east-1")

        # create some Lambda Layers to be used in the Terraform project
        cls.layerUtils = LayerUtils(cls.region_name, str(Path(cls.terraform_application_path).joinpath("artifacts")))
        cls.layer_postfix = str(uuid.uuid4())

        for lambda_layer_name in cls.pre_create_lambda_layers:
            cls.layerUtils.upsert_layer(
                f"{lambda_layer_name}-{cls.layer_postfix}",
                f"{lambda_layer_name}-{cls.layer_postfix}",
                f"{lambda_layer_name}.zip",
            )

        # create override file in const_layer module to test using the module default provided value
        const_layer_module_input_layer_overwrite = str(
            Path(cls.terraform_application_path).joinpath("const_layer", "variable_name_override.tf")
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
            Path(cls.terraform_application_path).joinpath("lambda_function_with_const_layer", "function_override.tf")
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
            init_command = ["terraform", "apply", "-auto-approve", "-input=false"]
            stdout, _, return_code = cls.run_command(command_list=init_command, env=cls._add_tf_project_variables())
            apply_command = ["terraform", "apply", "-auto-approve", "-input=false"]
            stdout, _, return_code = cls.run_command(command_list=apply_command, env=cls._add_tf_project_variables())

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
            stdout, _, return_code = cls.run_command(command_list=apply_command, env=cls._add_tf_project_variables())

        # delete the created layers
        cls.layerUtils.delete_layers()

        # delete the override file
        try:
            os.remove(str(Path(cls.terraform_application_path).joinpath("const_layer", "variable_name_override.tf")))
            os.remove(
                str(
                    Path(cls.terraform_application_path).joinpath(
                        "lambda_function_with_const_layer", "function_override.tf"
                    )
                )
            )
        except FileNotFoundError:
            pass

        # delete the function code bucket
        cls.s3_bucket.objects.all().delete()
        time.sleep(S3_SLEEP)
        cls.s3_bucket.delete()

    def tearDown(self) -> None:
        try:
            shutil.rmtree(str(Path(self.terraform_application_path).joinpath(".aws-sam-iacs")))  # type: ignore
            shutil.rmtree(str(Path(self.terraform_application_path).joinpath(".terraform")))  # type: ignore
            os.remove(str(Path(self.terraform_application_path).joinpath(".terraform.lock.hcl")))  # type: ignore
        except (FileNotFoundError, PermissionError):
            pass

    @parameterized.expand(functions)
    @pytest.mark.flaky(reruns=3)
    def test_invoke_function(self, function_name, expected_output):
        local_invoke_command_list = self.get_command_list(
            function_to_invoke=function_name, hook_name="terraform", beta_features=True
        )
        stdout, _, return_code = self.run_command(local_invoke_command_list, env=self._add_tf_project_variables())

        # Get the response without the sam-cli prompts that proceed it
        response = json.loads(stdout.decode("utf-8").split("\n")[-1])

        expected_response = json.loads('{"statusCode":200,"body":"{\\"message\\": \\"' + expected_output + '\\"}"}')

        self.assertEqual(return_code, 0)
        self.assertEqual(response, expected_response)


@skipIf(
    (not RUN_BY_CANARY and not CI_OVERRIDE),
    "Skip Terraform test cases unless running in CI",
)
class TestInvalidTerraformApplicationThatReferToS3BucketNotCreatedYet(InvokeTerraformApplicationIntegBase):
    terraform_application = Path("terraform/invalid_no_local_code_project")

    def tearDown(self) -> None:
        try:
            shutil.rmtree(str(Path(self.terraform_application_path).joinpath(".aws-sam-iacs")))  # type: ignore
            shutil.rmtree(str(Path(self.terraform_application_path).joinpath(".terraform")))  # type: ignore
            os.remove(str(Path(self.terraform_application_path).joinpath(".terraform.lock.hcl")))  # type: ignore
        except (FileNotFoundError, PermissionError):
            pass

    @pytest.mark.flaky(reruns=3)
    def test_invoke_function(self):
        function_name = "aws_lambda_function.function"
        local_invoke_command_list = self.get_command_list(
            function_to_invoke=function_name, hook_name="terraform", beta_features=True
        )
        _, stderr, return_code = self.run_command(local_invoke_command_list)
        process_stderr = stderr.strip()
        self.assertRegex(
            process_stderr.decode("utf-8"),
            "Error: Lambda resource aws_lambda_function.function is referring to an S3 bucket that is not created yet, "
            "and there is no sam metadata resource set for it to build its code locally",
        )
        self.assertNotEqual(return_code, 0)


@skipIf(
    ((not RUN_BY_CANARY) or (IS_WINDOWS and RUNNING_ON_CI) and not CI_OVERRIDE),
    "Skip local invoke terraform application tests on windows when running in CI unless overridden",
)
class TestInvokeTerraformApplicationWithLocalImageUri(InvokeTerraformApplicationIntegBase):
    terraform_application = Path("terraform/image_lambda_function_local_image_uri")
    functions = [
        "module.image_lambda2.aws_lambda_function.this[0]",
        "image_lambda2",
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

    def tearDown(self) -> None:
        try:
            shutil.rmtree(str(Path(self.terraform_application_path).joinpath(".aws-sam-iacs")))  # type: ignore
            shutil.rmtree(str(Path(self.terraform_application_path).joinpath(".terraform")))  # type: ignore
            os.remove(str(Path(self.terraform_application_path).joinpath(".terraform.lock.hcl")))  # type: ignore
        except (FileNotFoundError, PermissionError):
            pass

    @parameterized.expand(functions)
    @pytest.mark.flaky(reruns=3)
    def test_invoke_image_function(self, function_name):
        local_invoke_command_list = self.get_command_list(
            function_to_invoke=function_name,
            hook_name="terraform",
            event_path=self.event_path,
            beta_features=True,
        )
        stdout, _, return_code = self.run_command(local_invoke_command_list)

        # Get the response without the sam-cli prompts that proceed it
        self.assertEqual(return_code, 0)
        process_stdout = stdout.strip()
        self.assertEqual(process_stdout.decode("utf-8"), '"Hello world"')
