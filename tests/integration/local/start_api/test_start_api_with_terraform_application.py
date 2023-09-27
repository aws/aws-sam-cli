import logging
import shutil
import os
from pathlib import Path
from subprocess import CalledProcessError, CompletedProcess, run
from typing import Optional
from unittest import skipIf
from parameterized import parameterized, parameterized_class

import pytest
import requests

from tests.integration.local.common_utils import random_port
from tests.integration.local.start_api.start_api_integ_base import StartApiIntegBaseClass
from tests.testing_utils import get_sam_command, CI_OVERRIDE

LOG = logging.getLogger(__name__)


class TerraformStartApiIntegrationBase(StartApiIntegBaseClass):
    run_command_timeout = 300
    terraform_application: Optional[str] = None
    terraform_plan_file: Optional[str] = None

    @classmethod
    def setUpClass(cls):
        command = get_sam_command()
        cls.template_path = ""
        cls.build_before_invoke = False
        cls.command_list = [command, "local", "start-api", "--hook-name", "terraform"]
        if cls.terraform_plan_file:
            cls.command_list += ["--terraform-plan-file", cls.terraform_plan_file]
        cls.test_data_path = Path(cls.get_integ_dir()) / "testdata" / "start_api"
        cls.project_directory = cls.test_data_path / "terraform" / cls.terraform_application
        super(TerraformStartApiIntegrationBase, cls).setUpClass()

    @staticmethod
    def get_integ_dir():
        return Path(__file__).resolve().parents[2]

    @classmethod
    def tearDownClass(cls) -> None:
        super(TerraformStartApiIntegrationBase, cls).tearDownClass()
        cls._remove_generated_directories()

    @classmethod
    def _remove_generated_directories(cls):
        shutil.rmtree(str(Path(cls.project_directory / ".aws-sam-iacs")), ignore_errors=True)
        shutil.rmtree(str(Path(cls.project_directory / ".terraform")), ignore_errors=True)
        try:
            os.remove(str(Path(cls.project_directory / ".terraform.lock.hcl")))
        except (FileNotFoundError, PermissionError):
            pass

    @classmethod
    def _run_command(cls, command, check) -> CompletedProcess:
        test_data_folder = (
            Path(cls.get_integ_dir()) / "testdata" / "start_api" / "terraform" / cls.terraform_application  # type: ignore
        )
        return run(command, cwd=test_data_folder, check=check, capture_output=True, timeout=cls.run_command_timeout)


class TerraformStartApiIntegrationApplyBase(TerraformStartApiIntegrationBase):
    terraform_application: str

    @classmethod
    def setUpClass(cls):
        # init terraform project to populate deploy-only values
        cls._run_command(["terraform", "init", "-input=false"], check=True)
        cls._run_command(["terraform", "apply", "-auto-approve", "-input=false"], check=True)

        super(TerraformStartApiIntegrationApplyBase, cls).setUpClass()

    @staticmethod
    def get_integ_dir():
        return Path(__file__).resolve().parents[2]

    @classmethod
    def tearDownClass(cls) -> None:
        try:
            cls._run_command(["terraform", "apply", "-destroy", "-auto-approve", "-input=false"], check=True)
        except CalledProcessError:
            # skip, command can fail here if there isn't an applied project to destroy
            # (eg. failed to apply in setup)
            pass

        try:
            os.remove(str(Path(cls.project_directory / "terraform.tfstate")))  # type: ignore
            os.remove(str(Path(cls.project_directory / "terraform.tfstate.backup")))  # type: ignore
        except (FileNotFoundError, PermissionError):
            pass

        super(TerraformStartApiIntegrationApplyBase, cls).tearDownClass()


@skipIf(
    not CI_OVERRIDE,
    "Skip Terraform test cases unless running in CI",
)
@pytest.mark.flaky(reruns=3)
@parameterized_class(
    [
        {
            "terraform_application": "terraform-v1-nested-apis",
            "testing_urls": ["", "parent/hello", "parent"],
        },
        {
            "terraform_application": "terraform-v1-api-simple",
            "testing_urls": ["hello"],
        },
        {
            "terraform_application": "terraform-v2-api-simple",
            "testing_urls": ["hello"],
        },
        {
            "terraform_application": "terraform-v2-api-quick-create",
            "testing_urls": ["hello"],
        },
    ]
)
class TestStartApiTerraformApplication(TerraformStartApiIntegrationBase):
    def setUp(self):
        self.url = "http://127.0.0.1:{}".format(self.port)

    def test_successful_request(self):
        for url in self.testing_urls:
            response = requests.get(f"{self.url}/{url}", timeout=300)

            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json(), {"message": "hello world"})


@skipIf(
    not CI_OVERRIDE,
    "Skip Terraform test cases unless running in CI",
)
@pytest.mark.flaky(reruns=3)
class TestStartApiTerraformApplicationCustomPlanFile(TerraformStartApiIntegrationBase):
    terraform_application = "terraform-v1-api-simple"
    terraform_plan_file = "custom-plan.json"
    testing_urls = ["hello"]

    def setUp(self):
        self.url = "http://127.0.0.1:{}".format(self.port)

    def test_successful_request(self):
        for url in self.testing_urls:
            response = requests.get(f"{self.url}/{url}", timeout=300)

            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json(), {"message": "hello world"})


@skipIf(
    not CI_OVERRIDE,
    "Skip Terraform test cases unless running in CI",
)
@pytest.mark.flaky(reruns=3)
@parameterized_class(
    [
        {
            "terraform_application": "lambda-auth-openapi",
            "expected_error_message": "Error: AWS SAM CLI is unable to process a Terraform project that uses an OpenAPI"
            " specification to define the API Gateway resource.",
        },
        {
            "terraform_application": "terraform-api-simple-multiple-resources-limitation",
            "expected_error_message": "Error: AWS SAM CLI could not process a Terraform project that contains a source "
            "resource that is linked to more than one destination resource.",
        },
        {
            "terraform_application": "terraform-api-simple-local-variables-limitation",
            "expected_error_message": "Error: AWS SAM CLI could not process a Terraform project that uses local "
            "variables to define linked resources.",
        },
        {
            "terraform_application": "terraform-v2-api-simple-multi-resource-link",
            "expected_error_message": "Error: AWS SAM CLI could not process a Terraform project that contains a source "
            "resource that is linked to more than one destination resource.",
        },
        {
            "terraform_application": "terraform-v2-api-simple-local-resource-link",
            "expected_error_message": "Error: AWS SAM CLI could not process a Terraform project that uses local "
            "variables to define linked resources.",
        },
        {
            "terraform_application": "terraform-v2-openapi",
            "expected_error_message": "Error: AWS SAM CLI is unable to process a Terraform project that uses an OpenAPI"
            " specification to define the API Gateway resource.",
        },
    ]
)
class TestStartApiTerraformApplicationLimitations(TerraformStartApiIntegrationBase):
    @classmethod
    def setUpClass(cls):
        command = get_sam_command()
        cls.command_list = [
            command,
            "local",
            "start-api",
            "--hook-name",
            "terraform",
            "-p",
            str(random_port()),
        ]
        cls.test_data_path = Path(cls.get_integ_dir()) / "testdata" / "start_api"
        cls.project_directory = cls.test_data_path / "terraform" / cls.terraform_application

    @classmethod
    def tearDownClass(cls) -> None:
        cls._remove_generated_directories()

    def test_unsupported_limitations(self):
        apply_disclaimer_message = "Unresolvable attributes discovered in project, run terraform apply to resolve them."

        process = self._run_command(self.command_list, check=False)

        LOG.info(process.stderr)
        output = process.stderr.decode("utf-8")
        self.assertEqual(process.returncode, 1)
        self.assertRegex(output, self.expected_error_message)
        self.assertRegex(output, apply_disclaimer_message)


@skipIf(
    not CI_OVERRIDE,
    "Skip Terraform test cases unless running in CI",
)
@pytest.mark.flaky(reruns=3)
@parameterized_class(
    [
        {
            "terraform_application": "terraform-v1-nested-apis",
            "testing_urls": ["", "parent/hello", "parent"],
        },
        {
            "terraform_application": "terraform-v1-api-simple",
            "testing_urls": ["hello"],
        },
        {
            "terraform_application": "terraform-api-simple-multiple-resources-limitation",
            "testing_urls": ["hello"],
        },
        {
            "terraform_application": "terraform-api-simple-local-variables-limitation",
            "testing_urls": ["hello"],
        },
        {
            "terraform_application": "terraform-v2-api-simple-multi-resource-link",
            "testing_urls": ["hello"],
        },
        {
            "terraform_application": "terraform-v2-api-simple-local-resource-link",
            "testing_urls": ["hello"],
        },
        {
            "terraform_application": "terraform-v2-openapi",
            "testing_urls": ["hello"],
        },
        {
            "terraform_application": "terraform-v2-api-simple",
            "testing_urls": ["hello"],
        },
        {
            "terraform_application": "terraform-v2-api-quick-create",
            "testing_urls": ["hello"],
        },
    ]
)
class TestStartApiTerraformApplicationLimitationsAfterApply(TerraformStartApiIntegrationApplyBase):
    def setUp(self):
        self.url = "http://127.0.0.1:{}".format(self.port)

    def test_successful_request(self):
        for url in self.testing_urls:
            response = requests.get(f"{self.url}/{url}", timeout=300)

            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json(), {"message": "hello world"})


@skipIf(
    not CI_OVERRIDE,
    "Skip Terraform test cases unless running in CI",
)
@parameterized_class(
    [
        {
            "terraform_application": "v1-lambda-authorizer",
            "gateway_version": "v1",
        },
        {
            "terraform_application": "v2-lambda-authorizer",
            "gateway_version": "v2",
        },
    ]
)
@pytest.mark.flaky(reruns=3)
class TestStartApiTerraformApplicationLambdaAuthorizers(TerraformStartApiIntegrationBase):
    def setUp(self):
        self.url = "http://127.0.0.1:{}".format(self.port)

    @parameterized.expand(
        [
            ("/hello", {"headers": {"myheader": "123"}}, ["v1", "v2"]),
            ("/hello-request", {"headers": {"myheader": "123"}, "params": {"mystring": "456"}}, ["v1", "v2"]),
        ]
    )
    def test_invoke_authorizer(self, endpoint, parameters, applicable_gateway_versions):
        if self.gateway_version not in applicable_gateway_versions:
            self.skipTest(f"This test case is not supported for {self.gateway_version} api gateway")
        response = requests.get(self.url + endpoint, timeout=300, **parameters)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"message": "from authorizer"})

    @parameterized.expand(
        [
            ("/hello", {"headers": {"blank": "invalid"}}, ["v1", "v2"]),
            ("/hello-request", {"headers": {"blank": "invalid"}, "params": {"blank": "invalid"}}, ["v1", "v2"]),
        ]
    )
    def test_missing_authorizer_identity_source(self, endpoint, parameters, applicable_gateway_versions):
        if self.gateway_version not in applicable_gateway_versions:
            self.skipTest(f"This test case is not supported for {self.gateway_version} api gateway")
        response = requests.get(self.url + endpoint, timeout=300, **parameters)

        self.assertEqual(response.status_code, 401)

    def test_fails_token_header_validation_authorizer(self):
        if self.gateway_version not in ["v1"]:
            self.skipTest(f"This test case is not supported for {self.gateway_version} api gateway")
        response = requests.get(self.url + "/hello", timeout=300, headers={"myheader": "not valid"})

        self.assertEqual(response.status_code, 401)


@skipIf(
    not CI_OVERRIDE,
    "Skip Terraform test cases unless running in CI",
)
@parameterized_class(
    [
        {
            "terraform_application": "v1-lambda-authorizer",
            "gateway_version": "v1",
        },
        {
            "terraform_application": "lambda-auth-openapi",
            "gateway_version": "v1",
        },
        {
            "terraform_application": "terraform-v2-auth-openapi",
            "gateway_version": "v2",
        },
        {
            "terraform_application": "v2-lambda-authorizer",
            "gateway_version": "v2",
        },
    ]
)
@pytest.mark.flaky(reruns=3)
class TestStartApiTerraformApplicationAuthorizerAfterApply(TerraformStartApiIntegrationApplyBase):
    def setUp(self):
        self.url = "http://127.0.0.1:{}".format(self.port)

    @parameterized.expand(
        [
            ("/hello", {"headers": {"myheader": "123"}}, ["v1", "v2"]),
            ("/hello-request", {"headers": {"myheader": "123"}, "params": {"mystring": "456"}}, ["v1", "v2"]),
        ]
    )
    def test_successful_request(self, endpoint, params, applicable_gateway_versions):
        if self.gateway_version not in applicable_gateway_versions:
            self.skipTest(f"This test case is not supported for {self.gateway_version} api gateway")
        response = requests.get(self.url + endpoint, timeout=300, **params)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"message": "from authorizer"})

    @parameterized.expand(
        [
            ("/hello", {"headers": {"missin": "123"}}, ["v1", "v2"]),
            ("/hello-request", {"headers": {"notcorrect": "123"}, "params": {"abcde": "456"}}, ["v1", "v2"]),
        ]
    )
    def test_missing_identity_sources(self, endpoint, params, applicable_gateway_versions):
        if self.gateway_version not in applicable_gateway_versions:
            self.skipTest(f"This test case is not supported for {self.gateway_version} api gateway")
        response = requests.get(self.url + endpoint, timeout=300, **params)

        self.assertEqual(response.status_code, 401)

    def test_fails_token_header_validation_authorizer(self):
        if self.gateway_version not in ["v1"]:
            self.skipTest(f"This test case is not supported for {self.gateway_version} api gateway")
        response = requests.get(self.url + "/hello", timeout=300, headers={"myheader": "not valid"})

        self.assertEqual(response.status_code, 401)
