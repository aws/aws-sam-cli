import os
import logging
import shutil
import json
import uuid
import time

from pathlib import Path
from subprocess import Popen, PIPE, TimeoutExpired
from typing import Optional
from unittest import skipIf

import boto3
import docker

from parameterized import parameterized, parameterized_class

from samcli.commands._utils.experimental import EXPERIMENTAL_WARNING
from samcli.lib.utils.colors import Colored
from tests.integration.buildcmd.build_integ_base import BuildIntegBase
from tests.testing_utils import CI_OVERRIDE, IS_WINDOWS


LOG = logging.getLogger(__name__)
S3_SLEEP = 3


class BuildTerraformApplicationIntegBase(BuildIntegBase):
    terraform_application: Optional[Path] = None
    template = None
    build_in_container = False

    @classmethod
    def setUpClass(cls):
        super(BuildTerraformApplicationIntegBase, cls).setUpClass()
        cls.terraform_application_path = str(Path(cls.test_data_path, cls.terraform_application))
        if cls.build_in_container:
            cls.client = docker.from_env()
            cls.image_name = "sam-terraform-python-build"
            cls.docker_tag = f"{cls.image_name}:v1"
            cls.terraform_sam_build_image_context_path = str(
                Path(__file__)
                .resolve()
                .parents[2]
                .joinpath("integration", "testdata", "buildcmd", "terraform", "build_image_docker")
            )
            # Directly build an image that will be used across all local invokes in this class.
            for log in cls.client.api.build(
                path=cls.terraform_sam_build_image_context_path,
                dockerfile="Dockerfile",
                tag=cls.docker_tag,
                decode=True,
            ):
                LOG.info(log)

    def tearDown(self):
        """Clean up the generated files during integ test run"""
        try:
            shutil.rmtree(str(Path(self.terraform_application_path) / ".aws-sam"))
        except FileNotFoundError:
            pass

        try:
            shutil.rmtree(str(Path(self.terraform_application_path) / ".aws-sam-iacs"))
        except FileNotFoundError:
            pass

        try:
            shutil.rmtree(str(Path(self.terraform_application_path) / ".terraform"))
        except FileNotFoundError:
            pass

        try:
            (Path(self.terraform_application_path) / "terraform.tfstate").unlink()
        except FileNotFoundError:
            pass

        try:
            (Path(self.terraform_application_path) / "terraform.tfstate.backup").unlink()
        except FileNotFoundError:
            pass

        try:
            (Path(self.terraform_application_path) / ".terraform.lock.hcl").unlink()
        except FileNotFoundError:
            pass

        super().tearDown()

    def run_command(self, command_list, env=None, input=None):
        process = Popen(
            command_list, stdout=PIPE, stderr=PIPE, stdin=PIPE, env=env, cwd=self.terraform_application_path
        )
        try:
            (stdout, stderr) = process.communicate(input=input)
            return stdout, stderr, process.returncode
        except TimeoutExpired:
            process.kill()
            raise

    def _verify_invoke_built_function(self, function_logical_id, overrides, expected_result):
        LOG.info("Invoking built function '{}'".format(function_logical_id))

        cmdlist = [
            self.cmd,
            "local",
            "invoke",
            function_logical_id,
            "--no-event",
            "--hook-package-id",
            "terraform",
            "--beta-features",
        ]

        if overrides:
            cmdlist += [
                "--parameter-overrides",
                overrides,
            ]

        LOG.info("Running invoke Command: {}".format(cmdlist))

        stdout, _, _ = self.run_command(cmdlist)

        process_stdout = stdout.decode("utf-8")
        self.assertEqual(json.loads(process_stdout), expected_result)


class BuildTerraformApplicationS3BackendIntegBase(BuildTerraformApplicationIntegBase):
    @classmethod
    def setUpClass(cls):
        """Setting up a S3 bucket (using pre-created or create a new bucket) to use as a Terraform backend"""
        cls.region_name = os.environ.get("AWS_DEFAULT_REGION", "us-east-1")

        """Please read comments in package_integ_base.py for more details around this."""
        bucket_env_var = os.environ.get("AWS_S3")
        cls.pre_created_bucket = False
        if bucket_env_var:
            cls.pre_created_bucket = os.environ.get(bucket_env_var, False)
        cls.bucket_name = cls.pre_created_bucket if cls.pre_created_bucket else str(uuid.uuid4())

        s3 = boto3.resource("s3")
        cls.s3_bucket = s3.Bucket(cls.bucket_name)
        if not cls.pre_created_bucket:
            cls.s3_bucket.create()
            time.sleep(S3_SLEEP)

        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        """Clean up and delete the bucket if it is not pre-created"""
        cls.s3_bucket.objects.all().delete()
        time.sleep(S3_SLEEP)
        if not cls.pre_created_bucket:
            cls.s3_bucket.delete()

    def setUp(self):
        self.backend_key = str(Path("terraform-backend") / str(uuid.uuid4()))
        self.backendconfig_path = str(Path(self.terraform_application_path) / "backend.conf")
        with open(self.backendconfig_path, "w") as f:
            f.write(f'bucket="{self.bucket_name}"\n')
            f.write(f'key="{self.backend_key}"\n')
            f.write(f'region="{self.region_name}"')

        # We have to init the terraform project with specifying the S3 backend first
        _, stderr, _ = self.run_command(
            ["terraform", "init", f"-backend-config={self.backendconfig_path}", "-reconfigure"]
        )
        if stderr:
            LOG.error(stderr)

        super().setUp()

    def tearDown(self):
        """Clean up the terraform state file on S3 and remove the backendconfg locally"""
        self.s3_bucket.delete_objects(Delete={"Objects": [{"Key": self.backend_key}]})
        time.sleep(S3_SLEEP)
        try:
            Path(self.backendconfig_path).unlink()
        except FileNotFoundError:
            pass

        super().tearDown()


class TestBuildTerraformApplicationsWithInvalidOptions(BuildTerraformApplicationIntegBase):
    terraform_application = Path("terraform/simple_application")

    def test_invalid_coexist_parameters(self):
        self.template_path = "template.yaml"
        cmdlist = self.get_command_list(hook_package_id="terraform")
        _, stderr, return_code = self.run_command(cmdlist)

        process_stderr = stderr.strip()
        self.assertRegex(
            process_stderr.decode("utf-8"),
            "Error: Invalid value: Parameters hook-package-id, and t,template-file,template,parameter-overrides cannot "
            "be used together",
        )
        self.assertNotEqual(return_code, 0)

    def test_invalid_hook_package_id(self):
        cmdlist = self.get_command_list(hook_package_id="tf")
        _, stderr, return_code = self.run_command(cmdlist)
        process_stderr = stderr.strip()
        self.assertRegex(
            process_stderr.decode("utf-8"),
            "Error: Invalid value: tf is not a valid hook package id.",
        )
        self.assertNotEqual(return_code, 0)

    def test_exit_failed_use_container_no_build_image_hooks(self):
        cmdlist = self.get_command_list(beta_features=True, hook_package_id="terraform", use_container=True)
        _, stderr, return_code = self.run_command(cmdlist)
        process_stderr = stderr.strip()
        self.assertRegex(
            process_stderr.decode("utf-8"),
            "Error: Missing required parameter --build-image.",
        )
        self.assertNotEqual(return_code, 0)

    def test_exit_failed_use_container_short_format_no_build_image_hooks(self):
        cmdlist = self.get_command_list(beta_features=True, hook_package_id="terraform")
        cmdlist += ["-u"]
        _, stderr, return_code = self.run_command(cmdlist)
        process_stderr = stderr.strip()
        self.assertRegex(
            process_stderr.decode("utf-8"),
            "Error: Missing required parameter --build-image.",
        )
        self.assertNotEqual(return_code, 0)

    def test_exit_success_no_beta_feature_flags_hooks(self):
        cmdlist = self.get_command_list(beta_features=None, hook_package_id="terraform")
        stdout, stderr, return_code = self.run_command(cmdlist, input=b"N\n\n")
        terraform_beta_feature_prompted_text = (
            f"Supporting Terraform applications is a beta feature.{os.linesep}"
            f"Please confirm if you would like to proceed using AWS SAM CLI with terraform application.{os.linesep}"
            "You can also enable this beta feature with 'sam build --beta-features'."
        )
        self.assertRegex(stdout.decode("utf-8"), terraform_beta_feature_prompted_text)
        self.assertEqual(return_code, 0)
        self.assertRegex(stderr.strip().decode("utf-8"), "Terraform Support beta feature is not enabled.")

    def test_exit_success_no_beta_features_flags_supplied_hooks(self):
        cmdlist = self.get_command_list(beta_features=False, hook_package_id="terraform")
        _, stderr, return_code = self.run_command(cmdlist)
        self.assertEqual(return_code, 0)
        self.assertRegex(stderr.strip().decode("utf-8"), "Terraform Support beta feature is not enabled.")

    def test_build_terraform_with_no_beta_feature_option_in_samconfig_toml(self):
        samconfig_toml_path = Path(self.terraform_application_path).joinpath("samconfig.toml")
        samconfig_lines = [
            bytes("version = 0.1" + os.linesep, "utf-8"),
            bytes("[default.global.parameters]" + os.linesep, "utf-8"),
            bytes("beta_features = false" + os.linesep, "utf-8"),
        ]
        with open(samconfig_toml_path, "wb") as file:
            file.writelines(samconfig_lines)

        cmdlist = self.get_command_list(hook_package_id="terraform")
        _, stderr, return_code = self.run_command(cmdlist)
        self.assertEqual(return_code, 0)
        self.assertRegex(stderr.strip().decode("utf-8"), "Terraform Support beta feature is not enabled.")
        # delete the samconfig file
        try:
            os.remove(samconfig_toml_path)
        except FileNotFoundError:
            pass

    def test_build_terraform_with_no_beta_feature_option_as_environment_variable(self):
        environment_variables = os.environ.copy()
        environment_variables["SAM_CLI_BETA_TERRAFORM_SUPPORT"] = "False"

        build_command_list = self.get_command_list(hook_package_id="terraform")
        _, stderr, return_code = self.run_command(build_command_list, env=environment_variables)
        self.assertEqual(return_code, 0)
        self.assertRegex(stderr.strip().decode("utf-8"), "Terraform Support beta feature is not enabled.")


@skipIf(
    not CI_OVERRIDE,
    "Skip Terraform test cases unless running in CI",
)
@parameterized_class(
    ("build_in_container",),
    [
        (False,),
        (True,),
    ],
)
class TestBuildTerraformApplicationsWithZipBasedLambdaFunctionAndLocalBackend(BuildTerraformApplicationIntegBase):
    terraform_application = (
        Path("terraform/zip_based_lambda_functions_local_backend")
        if not IS_WINDOWS
        else Path("terraform/zip_based_lambda_functions_local_backend_windows")
    )
    functions = [
        ("module.function7.aws_lambda_function.this[0]", "hello world 7 - override version", True),
        ("function7", "hello world 7 - override version", True),
        ("module.function7.aws_lambda_function.this[0]", "hello world 7", False),
        ("function7", "hello world 7", False),
        ("module.function8.aws_lambda_function.this[0]", "hello world 8 - override version", True),
        ("function8", "hello world 8 - override version", True),
        ("module.function8.aws_lambda_function.this[0]", "hello world 8", False),
        ("function8", "hello world 8", False),
        ("module.function9.aws_lambda_function.this[0]", "hello world 9 - override version", True),
        ("function9", "hello world 9 - override version", True),
        ("module.function9.aws_lambda_function.this[0]", "hello world 9", False),
        ("function9", "hello world 9", False),
        ("module.function10.aws_lambda_function.this[0]", "hello world 10 - override version", True),
        ("function10", "hello world 10 - override version", True),
        ("module.function10.aws_lambda_function.this[0]", "hello world 10", False),
        ("function10", "hello world 10", False),
        ("aws_lambda_function.function6", "hello world 6 - override version", True),
        ("function6", "hello world 6 - override version", True),
        ("aws_lambda_function.function6", "hello world 6", False),
        ("function6", "hello world 6", False),
        ("aws_lambda_function.function5", "hello world 5 - override version", True),
        ("function5", "hello world 5 - override version", True),
        ("aws_lambda_function.function5", "hello world 5", False),
        ("function5", "hello world 5", False),
        ("aws_lambda_function.function4", "hello world 4 - override version", True),
        ("function4", "hello world 4 - override version", True),
        ("aws_lambda_function.function4", "hello world 4", False),
        ("function4", "hello world 4", False),
        ("aws_lambda_function.function3", "hello world 3 - override version", True),
        ("function3", "hello world 3 - override version", True),
        ("aws_lambda_function.function3", "hello world 3", False),
        ("function3", "hello world 3", False),
        ("module.function2.aws_lambda_function.this", "hello world 2 - override version", True),
        ("function2", "hello world 2 - override version", True),
        ("aws_lambda_function.function1", "hello world 1 - override version", True),
        ("function1", "hello world 1 - override version", True),
        ("module.function2.aws_lambda_function.this", "hello world 2", False),
        ("function2", "hello world 2", False),
        ("aws_lambda_function.function1", "hello world 1", False),
        ("function1", "hello world 1", False),
        ("aws_lambda_function.from_localfile", "[]", False),
        ("aws_lambda_function.from_s3", "[]", False),
        ("module.level1_lambda.aws_lambda_function.this", "[]", False),
        ("module.level1_lambda.module.level2_lambda.aws_lambda_function.this", "[]", False),
        ("my_function_from_localfile", "[]", False),
        ("my_function_from_s3", "[]", False),
        ("my_level1_lambda", "[]", False),
        ("my_level2_lambda", "[]", False),
    ]

    @classmethod
    def setUpClass(cls):
        if cls.build_in_container:
            cls.terraform_application = "terraform/zip_based_lambda_functions_local_backend"
        super().setUpClass()

    @parameterized.expand(functions)
    def test_build_and_invoke_lambda_functions(self, function_identifier, expected_output, should_override_code):
        command_list_parameters = {
            "beta_features": True,
            "hook_package_id": "terraform",
            "function_identifier": function_identifier,
        }
        if self.build_in_container:
            command_list_parameters["use_container"] = True
            command_list_parameters["build_image"] = self.docker_tag
            if should_override_code:
                command_list_parameters[
                    "container_env_var"
                ] = "TF_VAR_hello_function_src_code=./artifacts/HelloWorldFunction2"
        build_cmd_list = self.get_command_list(**command_list_parameters)
        LOG.info("command list: %s", build_cmd_list)
        environment_variables = os.environ.copy()
        if should_override_code:
            environment_variables["TF_VAR_hello_function_src_code"] = "./artifacts/HelloWorldFunction2"
        stdout, stderr, return_code = self.run_command(build_cmd_list, env=environment_variables)
        terraform_beta_feature_prompted_text = (
            "Supporting Terraform applications is a beta feature.\n"
            "Please confirm if you would like to proceed using AWS SAM CLI with terraform application.\n"
            "You can also enable this beta feature with 'sam build --beta-features'."
        )
        self.assertNotRegex(stdout.decode("utf-8"), terraform_beta_feature_prompted_text)
        self.assertTrue(stderr.decode("utf-8").startswith(Colored().yellow(EXPERIMENTAL_WARNING)))
        LOG.info(stderr)
        self.assertEqual(return_code, 0)

        self._verify_invoke_built_function(
            function_logical_id=function_identifier,
            overrides=None,
            expected_result={"statusCode": 200, "body": expected_output},
        )


@skipIf(
    not CI_OVERRIDE,
    "Skip Terraform test cases unless running in CI",
)
class TestInvalidTerraformApplicationThatReferToS3BucketNotCreatedYet(BuildTerraformApplicationIntegBase):
    terraform_application = Path("terraform/invalid_no_local_code_project")

    def test_invoke_function(self):
        function_identifier = "aws_lambda_function.function"
        build_cmd_list = self.get_command_list(
            beta_features=True, hook_package_id="terraform", function_identifier=function_identifier
        )

        LOG.info("command list: %s", build_cmd_list)
        environment_variables = os.environ.copy()

        _, stderr, return_code = self.run_command(build_cmd_list, env=environment_variables)
        LOG.info(stderr)
        process_stderr = stderr.strip()
        self.assertRegex(
            process_stderr.decode("utf-8"),
            "Error: Lambda resource aws_lambda_function.function is referring to an S3 bucket that is not created yet, "
            "and there is no sam metadata resource set for it to build its code locally",
        )
        self.assertNotEqual(return_code, 0)


@skipIf(
    not CI_OVERRIDE,
    "Skip Terraform test cases unless running in CI",
)
@parameterized_class(
    ("build_in_container",),
    [
        (False,),
        (True,),
    ],
)
class TestBuildTerraformApplicationsWithZipBasedLambdaFunctionAndS3Backend(BuildTerraformApplicationS3BackendIntegBase):
    terraform_application = (
        Path("terraform/zip_based_lambda_functions_s3_backend")
        if not IS_WINDOWS
        else Path("terraform/zip_based_lambda_functions_s3_backend_windows")
    )
    functions = [
        ("module.function7.aws_lambda_function.this[0]", "hello world 7 - override version", True),
        ("function7", "hello world 7 - override version", True),
        ("module.function7.aws_lambda_function.this[0]", "hello world 7", False),
        ("function7", "hello world 7", False),
        ("module.function8.aws_lambda_function.this[0]", "hello world 8 - override version", True),
        ("function8", "hello world 8 - override version", True),
        ("module.function8.aws_lambda_function.this[0]", "hello world 8", False),
        ("function8", "hello world 8", False),
        ("module.function9.aws_lambda_function.this[0]", "hello world 9 - override version", True),
        ("function9", "hello world 9 - override version", True),
        ("module.function9.aws_lambda_function.this[0]", "hello world 9", False),
        ("function9", "hello world 9", False),
        ("module.function10.aws_lambda_function.this[0]", "hello world 10 - override version", True),
        ("function10", "hello world 10 - override version", True),
        ("module.function10.aws_lambda_function.this[0]", "hello world 10", False),
        ("function10", "hello world 10", False),
        ("aws_lambda_function.function5", "hello world 5 - override version", True),
        ("function5", "hello world 5 - override version", True),
        ("aws_lambda_function.function5", "hello world 5", False),
        ("function5", "hello world 5", False),
        ("aws_lambda_function.function6", "hello world 6 - override version", True),
        ("function6", "hello world 6 - override version", True),
        ("aws_lambda_function.function6", "hello world 6", False),
        ("function6", "hello world 6", False),
        ("aws_lambda_function.function4", "hello world 4 - override version", True),
        ("function4", "hello world 4 - override version", True),
        ("aws_lambda_function.function4", "hello world 4", False),
        ("function4", "hello world 4", False),
        ("aws_lambda_function.function3", "hello world 3 - override version", True),
        ("function3", "hello world 3 - override version", True),
        ("aws_lambda_function.function3", "hello world 3", False),
        ("function3", "hello world 3", False),
        ("module.function2.aws_lambda_function.this", "hello world 2 - override version", True),
        ("function2", "hello world 2 - override version", True),
        ("aws_lambda_function.function1", "hello world 1 - override version", True),
        ("function1", "hello world 1 - override version", True),
        ("module.function2.aws_lambda_function.this", "hello world 2", False),
        ("function2", "hello world 2", False),
        ("aws_lambda_function.function1", "hello world 1", False),
        ("function1", "hello world 1", False),
        ("aws_lambda_function.from_localfile", "[]", False),
        ("aws_lambda_function.from_s3", "[]", False),
        ("module.level1_lambda.aws_lambda_function.this", "[]", False),
        ("module.level1_lambda.module.level2_lambda.aws_lambda_function.this", "[]", False),
        ("my_function_from_localfile", "[]", False),
        ("my_function_from_s3", "[]", False),
        ("my_level1_lambda", "[]", False),
        ("my_level2_lambda", "[]", False),
    ]

    @classmethod
    def setUpClass(cls):
        if cls.build_in_container:
            cls.terraform_application = "terraform/zip_based_lambda_functions_s3_backend"
        super().setUpClass()

    @parameterized.expand(functions)
    def test_build_and_invoke_lambda_functions(self, function_identifier, expected_output, should_override_code):
        command_list_parameters = {
            "beta_features": True,
            "hook_package_id": "terraform",
            "function_identifier": function_identifier,
        }
        if self.build_in_container:
            command_list_parameters["use_container"] = True
            command_list_parameters["build_image"] = self.docker_tag
            if should_override_code:
                command_list_parameters[
                    "container_env_var"
                ] = "TF_VAR_hello_function_src_code=./artifacts/HelloWorldFunction2"
        build_cmd_list = self.get_command_list(**command_list_parameters)
        LOG.info("command list: %s", build_cmd_list)
        environment_variables = os.environ.copy()
        if should_override_code:
            environment_variables["TF_VAR_hello_function_src_code"] = "./artifacts/HelloWorldFunction2"
        _, stderr, return_code = self.run_command(build_cmd_list, env=environment_variables)
        LOG.info(stderr)
        self.assertEqual(return_code, 0)

        self._verify_invoke_built_function(
            function_logical_id=function_identifier,
            overrides=None,
            expected_result={"statusCode": 200, "body": expected_output},
        )


@skipIf(
    not CI_OVERRIDE,
    "Skip Terraform test cases unless running in CI",
)
class TestInvalidBuildTerraformApplicationsWithZipBasedLambdaFunctionAndS3BackendNoS3Config(
    BuildTerraformApplicationIntegBase
):
    terraform_application = (
        Path("terraform/zip_based_lambda_functions_s3_backend")
        if not IS_WINDOWS
        else Path("terraform/zip_based_lambda_functions_s3_backend_windows")
    )

    def test_build_no_s3_config(self):
        command_list_parameters = {
            "beta_features": True,
            "hook_package_id": "terraform",
        }
        build_cmd_list = self.get_command_list(**command_list_parameters)
        LOG.info("command list: %s", build_cmd_list)
        environment_variables = os.environ.copy()
        _, stderr, return_code = self.run_command(build_cmd_list, env=environment_variables)
        LOG.info(stderr)
        self.assertNotEqual(return_code, 0)


@skipIf(
    not CI_OVERRIDE,
    "Skip Terraform test cases unless running in CI",
)
class TestBuildTerraformApplicationsWithImageBasedLambdaFunctionAndLocalBackend(BuildTerraformApplicationIntegBase):
    terraform_application = Path("terraform/image_based_lambda_functions_local_backend")
    functions = [
        "aws_lambda_function.function_with_non_image_uri",
        "aws_lambda_function.my_image_function",
        "module.l1_lambda.aws_lambda_function.this",
        "module.l1_lambda.module.l2_lambda.aws_lambda_function.this",
        "my_image_function",
        "my_l1_lambda",
        "my_l2_lambda",
        "module.serverless_tf_image_function.aws_lambda_function.this[0]",
        "serverless_tf_image_function",
    ]

    @parameterized.expand(functions)
    def test_build_and_invoke_lambda_functions(self, function_identifier):
        build_cmd_list = self.get_command_list(
            beta_features=True, hook_package_id="terraform", function_identifier=function_identifier
        )
        LOG.info("command list: %s", build_cmd_list)
        _, stderr, return_code = self.run_command(build_cmd_list)
        LOG.info(stderr)
        self.assertEqual(return_code, 0)

        self._verify_invoke_built_function(
            function_logical_id=function_identifier,
            overrides=None,
            expected_result={
                "statusCode": 200,
                "body": "Hello, My friend!",
                "headers": None,
                "multiValueHeaders": None,
            },
        )


@skipIf(
    not CI_OVERRIDE,
    "Skip Terraform test cases unless running in CI",
)
class TestBuildTerraformApplicationsWithImageBasedLambdaFunctionAndS3Backend(
    BuildTerraformApplicationS3BackendIntegBase
):
    terraform_application = Path("terraform/image_based_lambda_functions_s3_backend")
    functions = [
        "aws_lambda_function.function_with_non_image_uri",
        "aws_lambda_function.my_image_function",
        "module.l1_lambda.aws_lambda_function.this",
        "module.l1_lambda.module.l2_lambda.aws_lambda_function.this",
        "my_image_function",
        "my_l1_lambda",
        "my_l2_lambda",
        "module.serverless_tf_image_function.aws_lambda_function.this[0]",
        "serverless_tf_image_function",
    ]

    @parameterized.expand(functions)
    def test_build_and_invoke_lambda_functions(self, function_identifier):
        build_cmd_list = self.get_command_list(
            beta_features=True, hook_package_id="terraform", function_identifier=function_identifier
        )
        LOG.info("command list: %s", build_cmd_list)
        _, stderr, return_code = self.run_command(build_cmd_list)
        LOG.info(stderr)
        self.assertEqual(return_code, 0)

        self._verify_invoke_built_function(
            function_logical_id=function_identifier,
            overrides=None,
            expected_result={
                "statusCode": 200,
                "body": "Hello, My friend!",
                "headers": None,
                "multiValueHeaders": None,
            },
        )


@skipIf(
    not (CI_OVERRIDE),
    "Skip Terraform test cases unless running in CI",
)
class TestUnsupportedCases(BuildTerraformApplicationIntegBase):
    terraform_application = Path("terraform/unsupported")

    @parameterized.expand(
        [
            (
                "conditional_layers",
                r"AWS SAM CLI could not process a Terraform project that contains Lambda functions that are linked to more than one lambda layer",
            ),
            (
                "conditional_layers_null",
                r"AWS SAM CLI could not process a Terraform project that contains Lambda functions that are linked to more than one lambda layer",
            ),
            (
                "lambda_function_with_count_and_invalid_sam_metadata",
                r"There is no resource found that match the provided resource name aws_lambda_function.function1",
            ),
            (
                "one_lambda_function_linked_to_two_layers",
                r"AWS SAM CLI could not process a Terraform project that contains Lambda functions that are linked to more than one lambda layer",
            ),
            (
                "lambda_function_referencing_local_var_layer",
                r"AWS SAM CLI could not process a Terraform project that uses local variables to define the Lambda functions layers",
            ),
        ]
    )
    def test_unsupported_cases(self, app, expected_error_message):
        self.terraform_application_path = Path(self.terraform_application_path) / app
        build_cmd_list = self.get_command_list(beta_features=True, hook_package_id="terraform")
        LOG.info("command list: %s", build_cmd_list)
        _, stderr, return_code = self.run_command(build_cmd_list)
        LOG.info(stderr)
        self.assertEqual(return_code, 1)
        self.assertRegex(stderr.decode("utf-8"), expected_error_message)
