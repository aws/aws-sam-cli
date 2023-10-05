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
import pytest

from parameterized import parameterized_class

from samcli.yamlhelper import yaml_parse
from tests.integration.buildcmd.build_integ_base import BuildIntegBase
from tests.testing_utils import CI_OVERRIDE, IS_WINDOWS, RUN_BY_CANARY
from tests.testing_utils import run_command as static_run_command

LOG = logging.getLogger(__name__)
S3_SLEEP = 3


class BuildTerraformApplicationIntegBase(BuildIntegBase):
    terraform_application: Optional[Path] = None
    template = None
    build_in_container = False
    function_identifier: Optional[str] = None
    override: bool = False
    s3_backend = False

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
        if not self.s3_backend:
            self.build_with_prepare_hook()

    def tearDown(self):
        super(BuildTerraformApplicationIntegBase, self).tearDown()

    def run_command(self, command_list, env=None, timeout=None):
        command_result = static_run_command(command_list, env=env, cwd=self.working_dir, timeout=timeout)
        return command_result.stdout, command_result.stderr, command_result.process.returncode

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
        _, stderr, return_code = self.run_command(build_cmd_list, env=environment_variables)
        LOG.info(stderr.decode("utf-8"))
        self.assertEqual(return_code, 0)

    def validate_metadata_file(self):
        build_template_path = Path(self.working_dir) / ".aws-sam" / "build" / "template.yaml"
        expected_template_path = Path(self.working_dir) / "expected.template.yaml"
        build_template = self.read_template(build_template_path)
        expected_template = self.read_template(expected_template_path)
        self.clean_template(build_template)
        self.clean_template(expected_template)
        self.assertEqual(build_template, expected_template)
        LOG.info("Successfully validated template produced is same as expected")

    @staticmethod
    def clean_template(template: dict):
        # Some fields contain absolute paths that will differ across environments
        # We need to clean those fields up before we can compare the templates
        resources = template.get("Resources", {})
        for _, resource in resources.items():
            properties = resource.get("Properties", {})
            metadata = resource.get("Metadata", {})
            if properties:
                BuildTerraformApplicationIntegBase.remove_field(properties, "Code")
                BuildTerraformApplicationIntegBase.remove_field(properties, "Content")
            if metadata:
                BuildTerraformApplicationIntegBase.remove_field(metadata, "ContextPath")
                BuildTerraformApplicationIntegBase.remove_field(metadata, "WorkingDirectory")
                BuildTerraformApplicationIntegBase.remove_field(metadata, "ProjectRootDirectory")
                BuildTerraformApplicationIntegBase.remove_field(metadata, "DockerContext")

    @staticmethod
    def remove_field(section: dict, field: str):
        section_field = section.get(field)
        if section_field:
            section[field] = ""

    @staticmethod
    def read_template(path: Path):
        try:
            with open(path, "r") as f:
                template_dict = yaml_parse(f.read())
                return template_dict
        except OSError:
            raise AssertionError(f"Failed to read generated metadata file in: {path}")

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
            LOG.info(stderr.decode("utf-8"))
        self.build_with_prepare_hook()

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

    @classmethod
    def setUpClass(cls):
        if IS_WINDOWS and cls.build_in_container:
            # we use this TF project to test sam build in container on windows as we need to run a linux bash script for
            # build, and also we need to remove the Serverless TF functions from this project.
            # that is why we need to use a new project and not one of the existing linux or windows projects
            cls.terraform_application = "terraform/zip_based_lambda_functions_local_backend_container_windows"
        super().setUpClass()

    def test_build_and_invoke_lambda_functions(self):
        self.validate_metadata_file()
        self._verify_invoke_built_function(
            function_logical_id=self.function_identifier,
            overrides=None,
            expected_result={"statusCode": 200, "body": "hello world 9 - override version"},
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

    @classmethod
    def setUpClass(cls):
        if IS_WINDOWS and cls.build_in_container:
            # we use this TF project to test sam build in container on windows as we need to run a linux bash script for
            # build, and also we need to remove the Serverless TF functions from this project.
            # that is why we need to use a new project and not one of the existing linux or windows projects
            cls.terraform_application = "terraform/zip_based_lambda_functions_local_backend_container_windows"
        super().setUpClass()

    def test_build_and_invoke_lambda_functions(self):
        self.validate_metadata_file()
        self._verify_invoke_built_function(
            function_logical_id=self.function_identifier,
            overrides=None,
            expected_result={"statusCode": 200, "body": "hello world 9"},
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
    s3_backend = True
    terraform_application = (
        Path("terraform/zip_based_lambda_functions_s3_backend")
        if not IS_WINDOWS
        else Path("terraform/zip_based_lambda_functions_s3_backend_windows")
    )

    @classmethod
    def setUpClass(cls):
        if IS_WINDOWS and cls.build_in_container:
            # we use this TF project to test sam build in container on windows as we need to run a linux bash script for
            # build, and also we need to remove the Serverless TF functions from this project.
            # that is why we need to use a new project and not one of the existing linux or windows projects
            cls.terraform_application = "terraform/zip_based_lambda_functions_s3_backend_container_windows"
        super().setUpClass()

    def test_build_and_invoke_lambda_functions(self):
        self.validate_metadata_file()
        self._verify_invoke_built_function(
            function_logical_id=self.function_identifier,
            overrides=None,
            expected_result={"statusCode": 200, "body": "hello world 9 - override version"},
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
    s3_backend = True
    terraform_application = (
        Path("terraform/zip_based_lambda_functions_s3_backend")
        if not IS_WINDOWS
        else Path("terraform/zip_based_lambda_functions_s3_backend_windows")
    )

    @classmethod
    def setUpClass(cls):
        if IS_WINDOWS and cls.build_in_container:
            # we use this TF project to test sam build in container on windows as we need to run a linux bash script for
            # build, and also we need to remove the Serverless TF functions from this project.
            # that is why we need to use a new project and not one of the existing linux or windows projects
            cls.terraform_application = "terraform/zip_based_lambda_functions_s3_backend_container_windows"
        super().setUpClass()

    def test_build_and_invoke_lambda_functions(self):
        self.validate_metadata_file()
        self._verify_invoke_built_function(
            function_logical_id=self.function_identifier,
            overrides=None,
            expected_result={"statusCode": 200, "body": "hello world 9"},
        )


@skipIf(
    (not RUN_BY_CANARY and not CI_OVERRIDE),
    "Skip Terraform test cases unless running in CI",
)
class TestBuildTerraformApplicationsWithImageBasedLambdaFunctionAndLocalBackend(BuildTerraformApplicationIntegBase):
    function_identifier = "aws_lambda_function.function_with_non_image_uri"
    terraform_application = Path("terraform/image_based_lambda_functions_local_backend")

    def test_build_and_invoke_lambda_functions(self):
        self.validate_metadata_file()
        self._verify_invoke_built_function(
            function_logical_id=self.function_identifier,
            overrides=None,
            expected_result={
                "statusCode": 200,
                "body": "Hello, My friend!",
                "headers": None,
                "multiValueHeaders": None,
            },
        )


@skipIf(
    (not RUN_BY_CANARY and not CI_OVERRIDE),
    "Skip Terraform test cases unless running in CI",
)
class TestBuildTerraformApplicationsWithImageBasedLambdaFunctionAndS3Backend(
    BuildTerraformApplicationS3BackendIntegBase
):
    function_identifier = "aws_lambda_function.function_with_non_image_uri"
    s3_backend = True
    terraform_application = Path("terraform/image_based_lambda_functions_s3_backend")

    def test_build_and_invoke_lambda_functions(self):
        self.validate_metadata_file()
        self._verify_invoke_built_function(
            function_logical_id=self.function_identifier,
            overrides=None,
            expected_result={
                "statusCode": 200,
                "body": "Hello, My friend!",
                "headers": None,
                "multiValueHeaders": None,
            },
        )
