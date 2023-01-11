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

from samcli.lib.utils.colors import Colored
from tests.integration.buildcmd.build_integ_base import BuildIntegBase
from tests.testing_utils import CI_OVERRIDE, IS_WINDOWS, RUN_BY_CANARY

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

    def setUp(self):
        super().setUp()
        shutil.rmtree(Path(self.working_dir))
        shutil.copytree(Path(self.terraform_application_path), Path(self.working_dir))

    def run_command(self, command_list, env=None, input=None):
        process = Popen(command_list, stdout=PIPE, stderr=PIPE, stdin=PIPE, env=env, cwd=self.working_dir)
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
            "--hook-name",
            "terraform",
            "--beta-features",
        ]

        if overrides:
            cmdlist += [
                "--parameter-overrides",
                overrides,
            ]

        LOG.info("Running invoke Command: {}".format(cmdlist))

        stdout, stderr, _ = self.run_command(cmdlist)

        process_stdout = stdout.decode("utf-8")
        LOG.info("sam local invoke stdout: %s", stdout.decode("utf-8"))
        LOG.info("sam local invoke stderr: %s", stderr.decode("utf-8"))
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
        super().setUp()
        self.backend_key = f"terraform-backend/{str(uuid.uuid4())}"
        self.backendconfig_path = str(Path(self.working_dir) / "backend.conf")
        with open(self.backendconfig_path, "w") as f:
            f.write(f'bucket="{self.bucket_name}"\n')
            f.write(f'key="{self.backend_key}"\n')
            f.write(f'region="{self.region_name}"')

        # We have to init the terraform project with specifying the S3 backend first
        _, stderr, _ = self.run_command(
            ["terraform", "init", f"-backend-config={self.backendconfig_path}", "-reconfigure", "-input=false"]
        )
        if stderr:
            LOG.info(stderr)

    def tearDown(self):
        """Clean up the terraform state file on S3 and remove the backendconfg locally"""
        self.s3_bucket.delete_objects(Delete={"Objects": [{"Key": self.backend_key}]})
        time.sleep(S3_SLEEP)
        try:
            Path(self.backendconfig_path).unlink()
        except FileNotFoundError:
            pass

        super().tearDown()


@skipIf(
    (not RUN_BY_CANARY and not CI_OVERRIDE),
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
        ("module.function9.aws_lambda_function.this[0]", "hello world 9 - override version", True),
        ("function9", "hello world 9 - override version", True),
        ("module.function9.aws_lambda_function.this[0]", "hello world 9", False),
        ("function9", "hello world 9", False),
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
        if IS_WINDOWS and cls.build_in_container:
            # we use this TF project to test sam build in container on windows as we need to run a linux bash script for
            # build, and also we need to remove the Serverless TF functions from this project.
            # that is why we need to use a new project and not one of the existing linux or windows projects
            cls.terraform_application = "terraform/zip_based_lambda_functions_local_backend_container_windows"
        if not IS_WINDOWS:
            # The following functions are defined using serverless tf module, and since Serverless TF has some issue
            # while executing `terraform plan` in windows, we removed these function from the TF projects we used in
            # testing on Windows, and only test them on linux.
            # check the Serverless TF issue https://github.com/terraform-aws-modules/terraform-aws-lambda/issues/142
            cls.functions += [
                ("module.function7.aws_lambda_function.this[0]", "hello world 7 - override version", True),
                ("function7", "hello world 7 - override version", True),
                ("module.function7.aws_lambda_function.this[0]", "hello world 7", False),
                ("function7", "hello world 7", False),
                ("module.function8.aws_lambda_function.this[0]", "hello world 8 - override version", True),
                ("function8", "hello world 8 - override version", True),
                ("module.function8.aws_lambda_function.this[0]", "hello world 8", False),
                ("function8", "hello world 8", False),
                ("module.function10.aws_lambda_function.this[0]", "hello world 10 - override version", True),
                ("function10", "hello world 10 - override version", True),
                ("module.function10.aws_lambda_function.this[0]", "hello world 10", False),
                ("function10", "hello world 10", False),
                ("module.function11.aws_lambda_function.this[0]", "hello world 11 - override version", True),
                ("function11", "hello world 11 - override version", True),
                ("module.function11.aws_lambda_function.this[0]", "hello world 11", False),
                ("function11", "hello world 11", False),
            ]
        super().setUpClass()

    @parameterized.expand(functions)
    def test_build_and_invoke_lambda_functions(self, function_identifier, expected_output, should_override_code):
        command_list_parameters = {
            "beta_features": True,
            "hook_name": "terraform",
            "function_identifier": function_identifier,
        }
        if self.build_in_container:
            command_list_parameters["use_container"] = True
            command_list_parameters["build_image"] = self.docker_tag
            if should_override_code:
                command_list_parameters[
                    "container_env_var"
                ] = "TF_VAR_HELLO_FUNCTION_SRC_CODE=./artifacts/HelloWorldFunction2"
        build_cmd_list = self.get_command_list(**command_list_parameters)
        LOG.info("command list: %s", build_cmd_list)
        environment_variables = os.environ.copy()
        if should_override_code:
            environment_variables["TF_VAR_HELLO_FUNCTION_SRC_CODE"] = "./artifacts/HelloWorldFunction2"
        stdout, stderr, return_code = self.run_command(build_cmd_list, env=environment_variables)
        terraform_beta_feature_prompted_text = (
            f"Supporting Terraform applications is a beta feature.{os.linesep}"
            f"Please confirm if you would like to proceed using AWS SAM CLI with terraform application.{os.linesep}"
            "You can also enable this beta feature with 'sam build --beta-features'."
        )
        experimental_warning = (
            f"{os.linesep}Experimental features are enabled for this session.{os.linesep}"
            f"Visit the docs page to learn more about the AWS Beta terms "
            f"https://aws.amazon.com/service-terms/.{os.linesep}"
        )
        self.assertNotRegex(stdout.decode("utf-8"), terraform_beta_feature_prompted_text)
        self.assertIn(Colored().yellow(experimental_warning), stderr.decode("utf-8"))
        LOG.info("sam build stdout: %s", stdout.decode("utf-8"))
        LOG.info("sam build stderr: %s", stderr.decode("utf-8"))
        self.assertEqual(return_code, 0)

        self._verify_invoke_built_function(
            function_logical_id=function_identifier,
            overrides=None,
            expected_result={"statusCode": 200, "body": expected_output},
        )


@skipIf(
    (not RUN_BY_CANARY and not CI_OVERRIDE),
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
        ("module.function9.aws_lambda_function.this[0]", "hello world 9 - override version", True),
        ("function9", "hello world 9 - override version", True),
        ("module.function9.aws_lambda_function.this[0]", "hello world 9", False),
        ("function9", "hello world 9", False),
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
        if IS_WINDOWS and cls.build_in_container:
            # we use this TF project to test sam build in container on windows as we need to run a linux bash script for
            # build, and also we need to remove the Serverless TF functions from this project.
            # that is why we need to use a new project and not one of the existing linux or windows projects
            cls.terraform_application = "terraform/zip_based_lambda_functions_s3_backend_container_windows"
        if not IS_WINDOWS:
            # The following functions are defined using serverless tf module, and since Serverless TF has some issue
            # while executing `terraform plan` in windows, we removed these function from the TF projects we used in
            # testing on Windows, and only test them on linux.
            # check the Serverless TF issue https://github.com/terraform-aws-modules/terraform-aws-lambda/issues/142
            cls.functions += [
                ("module.function7.aws_lambda_function.this[0]", "hello world 7 - override version", True),
                ("function7", "hello world 7 - override version", True),
                ("module.function7.aws_lambda_function.this[0]", "hello world 7", False),
                ("function7", "hello world 7", False),
                ("module.function8.aws_lambda_function.this[0]", "hello world 8 - override version", True),
                ("function8", "hello world 8 - override version", True),
                ("module.function8.aws_lambda_function.this[0]", "hello world 8", False),
                ("function8", "hello world 8", False),
                ("module.function10.aws_lambda_function.this[0]", "hello world 10 - override version", True),
                ("function10", "hello world 10 - override version", True),
                ("module.function10.aws_lambda_function.this[0]", "hello world 10", False),
                ("function10", "hello world 10", False),
                ("module.function11.aws_lambda_function.this[0]", "hello world 11 - override version", True),
                ("function11", "hello world 11 - override version", True),
                ("module.function11.aws_lambda_function.this[0]", "hello world 11", False),
                ("function11", "hello world 11", False),
            ]
        super().setUpClass()

    @parameterized.expand(functions)
    def test_build_and_invoke_lambda_functions(self, function_identifier, expected_output, should_override_code):
        command_list_parameters = {
            "beta_features": True,
            "hook_name": "terraform",
            "function_identifier": function_identifier,
        }
        if self.build_in_container:
            command_list_parameters["use_container"] = True
            command_list_parameters["build_image"] = self.docker_tag
            if should_override_code:
                command_list_parameters[
                    "container_env_var"
                ] = "TF_VAR_HELLO_FUNCTION_SRC_CODE=./artifacts/HelloWorldFunction2"
        build_cmd_list = self.get_command_list(**command_list_parameters)
        LOG.info("command list: %s", build_cmd_list)
        environment_variables = os.environ.copy()
        if should_override_code:
            environment_variables["TF_VAR_HELLO_FUNCTION_SRC_CODE"] = "./artifacts/HelloWorldFunction2"
        _, stderr, return_code = self.run_command(build_cmd_list, env=environment_variables)
        LOG.info(stderr)
        self.assertEqual(return_code, 0)

        self._verify_invoke_built_function(
            function_logical_id=function_identifier,
            overrides=None,
            expected_result={"statusCode": 200, "body": expected_output},
        )
