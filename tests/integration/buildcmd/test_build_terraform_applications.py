import datetime
import os
import logging
import shutil
import json
import tempfile
import uuid
import time

from pathlib import Path
from subprocess import Popen, PIPE, TimeoutExpired
from typing import Optional
from unittest import skipIf

import boto3
import docker
import pytest

from parameterized import parameterized, parameterized_class

from tests.integration.buildcmd.build_integ_base import BuildIntegBase
from tests.testing_utils import CI_OVERRIDE, IS_WINDOWS, RUN_BY_CANARY
from tests.testing_utils import run_command as static_run_command

LOG = logging.getLogger(__name__)
S3_SLEEP = 3


class BuildTerraformApplicationIntegBase(BuildIntegBase):
    terraform_application: Optional[Path] = None
    template = None
    build_in_container = False
    function_identifier = None
    override = False
    terraform_application_execution_path = None

    @classmethod
    def setUpClass(cls):
        super(BuildTerraformApplicationIntegBase, cls).setUpClass()
        cls.terraform_application_path = str(Path(cls.test_data_path, cls.terraform_application))
        cls.terraform_application_execution_path = str(Path(__file__).resolve().parent.joinpath(str(uuid.uuid4()).replace("-", "")[:10]))
        shutil.copytree(Path(cls.terraform_application_path), Path(cls.terraform_application_execution_path))
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
        shutil.copytree(Path(self.terraform_application_execution_path), Path(self.working_dir))

    def run_command(self, command_list, env=None, input=None, timeout=None, override_dir=None):
        running_dir = override_dir if override_dir else self.working_dir
        process = Popen(command_list, stdout=PIPE, stderr=PIPE, stdin=PIPE, env=env, cwd=running_dir)
        try:
            (stdout, stderr) = process.communicate(input=input, timeout=timeout)
            return stdout, stderr, process.returncode
        except TimeoutExpired:
            process.kill()
            raise

    @pytest.fixture(scope="class", autouse=True)
    def build_with_prepare_hook(self):
        if not self.function_identifier:
            # This doesn't make sense for all tests that inherit this base class, skip for those
            return

        command_list_parameters = {"function_identifier": self.function_identifier, "hook_name": "terraform"}
        if self.build_in_container:
            command_list_parameters["use_container"] = True
            command_list_parameters["build_image"] = self.docker_tag
            if self.override:
                command_list_parameters[
                    "container_env_var"
                ] = "TF_VAR_HELLO_FUNCTION_SRC_CODE=./artifacts/HelloWorldFunction2"

        environment_variables = os.environ.copy()
        if self.override:
            environment_variables["TF_VAR_HELLO_FUNCTION_SRC_CODE"] = "./artifacts/HelloWorldFunction2"

        build_cmd_list = self.get_command_list(**command_list_parameters)
        _, stderr, return_code = self.run_command(
            build_cmd_list, override_dir=self.terraform_application_execution_path, env=environment_variables
        )
        LOG.info(stderr.decode("utf-8"))
        self.assertEqual(return_code, 0)

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

    @classmethod
    def tearDownClass(cls) -> None:
        cls.terraform_application_execution_path and shutil.rmtree(cls.terraform_application_execution_path, ignore_errors=True)

    def tearDown(self):
        super(BuildTerraformApplicationIntegBase, self).tearDown()


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
        cls.initialize_s3_backend()

    @classmethod
    def initialize_s3_backend(cls):
        cls.backend_key = f"terraform-backend/{str(uuid.uuid4())}"
        cls.backendconfig_path = str(Path(cls.terraform_application_execution_path) / "backend.conf")
        with open(cls.backendconfig_path, "w") as f:
            f.write(f'bucket="{cls.bucket_name}"\n')
            f.write(f'key="{cls.backend_key}"\n')
            f.write(f'region="{cls.region_name}"')

        # We have to init the terraform project with specifying the S3 backend first
        _, stderr, _ = static_run_command(
            ["terraform", "init", f"-backend-config={cls.backendconfig_path}", "-reconfigure", "-input=false"],
            cwd=cls.terraform_application_execution_path
        )
        if stderr:
            LOG.info(stderr)

    @classmethod
    def tearDownClass(cls):
        """Clean up and delete the bucket if it is not pre-created"""
        cls.s3_bucket.objects.all().delete()
        time.sleep(S3_SLEEP)
        if not cls.pre_created_bucket:
            cls.s3_bucket.delete()

    def setUp(self):
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
@pytest.mark.xdist_group(name="zip_lambda_local_backend_override")
class TestBuildTerraformApplicationsWithZipBasedLambdaFunctionAndLocalBackendWithOverride(
    BuildTerraformApplicationIntegBase
):
    function_identifier = "function9"
    override = True
    terraform_application = (
        Path("terraform/zip_based_lambda_functions_local_backend")
        if not IS_WINDOWS
        else Path("terraform/zip_based_lambda_functions_local_backend_windows")
    )
    functions = [
        ("module.function9.aws_lambda_function.this[0]", "hello world 9 - override version"),
        ("function9", "hello world 9 - override version",),
        ("aws_lambda_function.function6", "hello world 6 - override version"),
        ("function6", "hello world 6 - override version"),
        ("aws_lambda_function.function5", "hello world 5 - override version"),
        ("function5", "hello world 5 - override version"),
        ("aws_lambda_function.function4", "hello world 4 - override version"),
        ("function4", "hello world 4 - override version"),
        ("aws_lambda_function.function3", "hello world 3 - override version"),
        ("function3", "hello world 3 - override version"),
        ("module.function2.aws_lambda_function.this", "hello world 2 - override version"),
        ("function2", "hello world 2 - override version"),
        ("aws_lambda_function.function1", "hello world 1 - override version"),
        ("function1", "hello world 1 - override version"),
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
                ("module.function7.aws_lambda_function.this[0]", "hello world 7 - override version"),
                ("function7", "hello world 7 - override version"),
                ("module.function8.aws_lambda_function.this[0]", "hello world 8 - override version"),
                ("function8", "hello world 8 - override version"),
                ("module.function10.aws_lambda_function.this[0]", "hello world 10 - override version"),
                ("function10", "hello world 10 - override version"),
                ("module.function11.aws_lambda_function.this[0]", "hello world 11 - override version"),
                ("function11", "hello world 11 - override version"),
            ]
        super().setUpClass()

    @parameterized.expand(functions)
    def test_build_and_invoke_lambda_functions(self, function_identifier, expected_output):
        command_list_parameters = {
            "hook_name": "terraform",
            "function_identifier": function_identifier,
            "skip_prepare_infra": True,
        }
        if self.build_in_container:
            command_list_parameters["use_container"] = True
            command_list_parameters["build_image"] = self.docker_tag
            if self.override:
                command_list_parameters[
                    "container_env_var"
                ] = "TF_VAR_HELLO_FUNCTION_SRC_CODE=./artifacts/HelloWorldFunction2"

        environment_variables = os.environ.copy()
        if self.override:
            environment_variables["TF_VAR_HELLO_FUNCTION_SRC_CODE"] = "./artifacts/HelloWorldFunction2"

        build_cmd_list = self.get_command_list(**command_list_parameters)
        LOG.info("command list: %s", build_cmd_list)
        stdout, stderr, return_code = self.run_command(build_cmd_list, env=environment_variables)
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
@pytest.mark.xdist_group(name="zip_lambda_local_backend")
class TestBuildTerraformApplicationsWithZipBasedLambdaFunctionAndLocalBackend(BuildTerraformApplicationIntegBase):
    function_identifier = "function9"
    terraform_application = (
        Path("terraform/zip_based_lambda_functions_local_backend")
        if not IS_WINDOWS
        else Path("terraform/zip_based_lambda_functions_local_backend_windows")
    )
    functions = [
        ("module.function9.aws_lambda_function.this[0]", "hello world 9"),
        ("function9", "hello world 9"),
        # ("aws_lambda_function.function6", "hello world 6"),
        # ("function6", "hello world 6"),
        # ("aws_lambda_function.function5", "hello world 5"),
        # ("function5", "hello world 5"),
        # ("aws_lambda_function.function4", "hello world 4"),
        # ("function4", "hello world 4"),
        # ("aws_lambda_function.function3", "hello world 3"),
        # ("function3", "hello world 3"),
        # ("module.function2.aws_lambda_function.this", "hello world 2"),
        # ("function2", "hello world 2"),
        # ("aws_lambda_function.function1", "hello world 1"),
        # ("function1", "hello world 1"),
        # ("aws_lambda_function.from_localfile", "[]"),
        # ("aws_lambda_function.from_s3", "[]"),
        # ("module.level1_lambda.aws_lambda_function.this", "[]"),
        # ("module.level1_lambda.module.level2_lambda.aws_lambda_function.this", "[]"),
        # ("my_function_from_localfile", "[]"),
        # ("my_function_from_s3", "[]"),
        # ("my_level1_lambda", "[]"),
        # ("my_level2_lambda", "[]"),
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
                ("module.function7.aws_lambda_function.this[0]", "hello world 7"),
                ("function7", "hello world 7"),
                ("module.function8.aws_lambda_function.this[0]", "hello world 8"),
                ("function8", "hello world 8"),
                ("module.function10.aws_lambda_function.this[0]", "hello world 10"),
                ("function10", "hello world 10"),
                ("module.function11.aws_lambda_function.this[0]", "hello world 11"),
                ("function11", "hello world 11"),
            ]
        super().setUpClass()

    @parameterized.expand(functions)
    def test_build_and_invoke_lambda_functions(self, function_identifier, expected_output):
        command_list_parameters = {
            "hook_name": "terraform",
            "function_identifier": function_identifier,
            "skip_prepare_infra": True,
        }
        if self.build_in_container:
            command_list_parameters["use_container"] = True
            command_list_parameters["build_image"] = self.docker_tag
        build_cmd_list = self.get_command_list(**command_list_parameters)
        LOG.info("command list: %s", build_cmd_list)
        stdout, stderr, return_code = self.run_command(build_cmd_list)
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
@pytest.mark.xdist_group(name="zip_lambda_s3_backend")
class TestBuildTerraformApplicationsWithZipBasedLambdaFunctionAndS3BackendWithOverride(
    BuildTerraformApplicationS3BackendIntegBase
):
    function_identifier = "function9"
    override = True
    terraform_application = (
        Path("terraform/zip_based_lambda_functions_s3_backend")
        if not IS_WINDOWS
        else Path("terraform/zip_based_lambda_functions_s3_backend_windows")
    )
    functions = [
        ("module.function9.aws_lambda_function.this[0]", "hello world 9 - override version"),
        ("function9", "hello world 9 - override version"),
        ("aws_lambda_function.function5", "hello world 5 - override version"),
        ("function5", "hello world 5 - override version"),
        ("aws_lambda_function.function6", "hello world 6 - override version"),
        ("function6", "hello world 6 - override version"),
        ("aws_lambda_function.function4", "hello world 4 - override version"),
        ("function4", "hello world 4 - override version"),
        ("aws_lambda_function.function3", "hello world 3 - override version"),
        ("function3", "hello world 3 - override version"),
        ("module.function2.aws_lambda_function.this", "hello world 2 - override version"),
        ("function2", "hello world 2 - override version"),
        ("aws_lambda_function.function1", "hello world 1 - override version"),
        ("function1", "hello world 1 - override version"),
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
                ("module.function7.aws_lambda_function.this[0]", "hello world 7 - override version"),
                ("function7", "hello world 7 - override version"),
                ("module.function8.aws_lambda_function.this[0]", "hello world 8 - override version"),
                ("function8", "hello world 8 - override version"),
                ("module.function10.aws_lambda_function.this[0]", "hello world 10 - override version"),
                ("function10", "hello world 10 - override version"),
                ("module.function11.aws_lambda_function.this[0]", "hello world 11 - override version"),
                ("function11", "hello world 11 - override version"),
            ]
        super().setUpClass()

    @parameterized.expand(functions)
    def test_build_and_invoke_lambda_functions(self, function_identifier, expected_output):
        command_list_parameters = {
            "hook_name": "terraform",
            "function_identifier": function_identifier,
            "skip_prepare_infra": True,
        }
        if self.build_in_container:
            command_list_parameters["use_container"] = True
            command_list_parameters["build_image"] = self.docker_tag
            if self.override:
                command_list_parameters[
                    "container_env_var"
                ] = "TF_VAR_HELLO_FUNCTION_SRC_CODE=./artifacts/HelloWorldFunction2"
        build_cmd_list = self.get_command_list(**command_list_parameters)
        LOG.info("command list: %s", build_cmd_list)
        environment_variables = os.environ.copy()
        if self.override:
            environment_variables["TF_VAR_HELLO_FUNCTION_SRC_CODE"] = "./artifacts/HelloWorldFunction2"
        _, stderr, return_code = self.run_command(build_cmd_list, env=environment_variables)
        LOG.info(stderr)
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
@pytest.mark.xdist_group(name="zip_lambda_s3_backend_override")
class TestBuildTerraformApplicationsWithZipBasedLambdaFunctionAndS3Backend(BuildTerraformApplicationS3BackendIntegBase):
    function_identifier = "function9"
    terraform_application = (
        Path("terraform/zip_based_lambda_functions_s3_backend")
        if not IS_WINDOWS
        else Path("terraform/zip_based_lambda_functions_s3_backend_windows")
    )
    functions = [
        ("module.function9.aws_lambda_function.this[0]", "hello world 9"),
        ("function9", "hello world 9"),
        ("aws_lambda_function.function5", "hello world 5"),
        ("function5", "hello world 5"),
        ("aws_lambda_function.function6", "hello world 6"),
        ("function6", "hello world 6"),
        ("aws_lambda_function.function4", "hello world 4"),
        ("function4", "hello world 4"),
        ("aws_lambda_function.function3", "hello world 3"),
        ("function3", "hello world 3"),
        ("module.function2.aws_lambda_function.this", "hello world 2"),
        ("function2", "hello world 2"),
        ("aws_lambda_function.function1", "hello world 1"),
        ("function1", "hello world 1"),
        ("aws_lambda_function.from_localfile", "[]"),
        ("aws_lambda_function.from_s3", "[]"),
        ("module.level1_lambda.aws_lambda_function.this", "[]"),
        ("module.level1_lambda.module.level2_lambda.aws_lambda_function.this", "[]"),
        ("my_function_from_localfile", "[]"),
        ("my_function_from_s3", "[]"),
        ("my_level1_lambda", "[]"),
        ("my_level2_lambda", "[]"),
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
                ("module.function7.aws_lambda_function.this[0]", "hello world 7"),
                ("function7", "hello world 7"),
                ("module.function8.aws_lambda_function.this[0]", "hello world 8"),
                ("function8", "hello world 8"),
                ("module.function10.aws_lambda_function.this[0]", "hello world 10"),
                ("function10", "hello world 10"),
                ("module.function11.aws_lambda_function.this[0]", "hello world 11"),
                ("function11", "hello world 11"),
            ]
        super().setUpClass()

    @parameterized.expand(functions)
    def test_build_and_invoke_lambda_functions(self, function_identifier, expected_output):
        command_list_parameters = {
            "hook_name": "terraform",
            "function_identifier": function_identifier,
            "skip_prepare_infra": True,
        }
        if self.build_in_container:
            command_list_parameters["use_container"] = True
            command_list_parameters["build_image"] = self.docker_tag
        build_cmd_list = self.get_command_list(**command_list_parameters)
        LOG.info("command list: %s", build_cmd_list)
        start = time.time()
        _, stderr, return_code = self.run_command(build_cmd_list)
        end = time.time()
        LOG.info(f"END: {end}, DURATION {end - start}")
        self.assertEqual(return_code, 0)

        self._verify_invoke_built_function(
            function_logical_id=function_identifier,
            overrides=None,
            expected_result={"statusCode": 200, "body": expected_output},
        )
