import shutil
import os
from pathlib import Path
from subprocess import CalledProcessError, CompletedProcess, run
from typing import Optional
from unittest import skipIf
from parameterized import parameterized

import pytest
import requests

from tests.integration.local.start_api.start_api_integ_base import StartApiIntegBaseClass
from tests.testing_utils import get_sam_command, CI_OVERRIDE


class TerraformStartApiIntegrationBase(StartApiIntegBaseClass):
    terraform_application: Optional[str] = None

    @classmethod
    def setUpClass(cls):
        command = get_sam_command()
        cls.template_path = ""
        cls.build_before_invoke = False
        cls.command_list = [command, "local", "start-api", "--hook-name", "terraform", "--beta-features"]
        cls.test_data_path = Path(cls.get_integ_dir()) / "testdata" / "start_api"
        cls.project_directory = cls.test_data_path / "terraform" / cls.terraform_application
        super(TerraformStartApiIntegrationBase, cls).setUpClass()

    @staticmethod
    def get_integ_dir():
        return Path(__file__).resolve().parents[2]

    def tearDown(self) -> None:
        shutil.rmtree(str(Path(self.project_directory / ".aws-sam-iacs")), ignore_errors=True)  # type: ignore
        shutil.rmtree(str(Path(self.project_directory / ".terraform")), ignore_errors=True)  # type: ignore
        try:
            os.remove(str(Path(self.project_directory / ".terraform.lock.hcl")))  # type: ignore
        except (FileNotFoundError, PermissionError):
            pass


class TerraformStartApiIntegrationApplyBase(TerraformStartApiIntegrationBase):
    terraform_application: str
    run_command_timeout = 300

    @classmethod
    def setUpClass(cls):
        # init terraform project to populate deploy-only values
        cls._run_command(["terraform", "init", "-input=false"])
        cls._run_command(["terraform", "apply", "-auto-approve", "-input=false"])

        super(TerraformStartApiIntegrationApplyBase, cls).setUpClass()

    @staticmethod
    def get_integ_dir():
        return Path(__file__).resolve().parents[2]

    @classmethod
    def tearDownClass(cls) -> None:
        try:
            cls._run_command(["terraform", "apply", "-destroy", "-auto-approve", "-input=false"])
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

    @classmethod
    def _run_command(cls, command) -> CompletedProcess:
        test_data_folder = (
            Path(cls.get_integ_dir()) / "testdata" / "start_api" / "terraform" / cls.terraform_application
        )

        return run(command, cwd=test_data_folder, check=True, capture_output=True, timeout=cls.run_command_timeout)


@skipIf(
    not CI_OVERRIDE,
    "Skip Terraform test cases unless running in CI",
)
@pytest.mark.flaky(reruns=3)
class TestStartApiTerraformApplication(TerraformStartApiIntegrationBase):
    terraform_application = "terraform-v1-api-simple"

    def setUp(self):
        self.url = "http://127.0.0.1:{}".format(self.port)

    def test_successful_request(self):
        response = requests.get(self.url + "/hello", timeout=300)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"message": "hello world"})


@skipIf(
    not CI_OVERRIDE,
    "Skip Terraform test cases unless running in CI",
)
@pytest.mark.flaky(reruns=3)
class TestStartApiTerraformApplicationV1LambdaAuthorizers(TerraformStartApiIntegrationBase):
    terraform_application = "v1-lambda-authorizer"

    def setUp(self):
        self.url = "http://127.0.0.1:{}".format(self.port)

    @parameterized.expand(
        [
            ("/hello", {"headers": {"myheader": "123"}}),
            ("/hello-request", {"headers": {"myheader": "123"}, "params": {"mystring": "456"}}),
            ("/hello-request-empty", {}),
            ("/hello-request-empty", {"headers": {"foo": "bar"}}),
        ]
    )
    def test_invoke_authorizer(self, endpoint, parameters):
        response = requests.get(self.url + endpoint, timeout=300, **parameters)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"message": "from authorizer"})

    @parameterized.expand(
        [
            ("/hello", {"headers": {"blank": "invalid"}}),
            ("/hello-request", {"headers": {"blank": "invalid"}, "params": {"blank": "invalid"}}),
        ]
    )
    def test_missing_authorizer_identity_source(self, endpoint, parameters):
        response = requests.get(self.url + endpoint, timeout=300, **parameters)

        self.assertEqual(response.status_code, 401)

    def test_fails_token_header_validation_authorizer(self):
        response = requests.get(self.url + "/hello", timeout=300, headers={"myheader": "not valid"})

        self.assertEqual(response.status_code, 401)


@skipIf(
    not CI_OVERRIDE,
    "Skip Terraform test cases unless running in CI",
)
@pytest.mark.flaky(reruns=3)
class TestStartApiTerraformApplicationOpenApiAuthorizer(TerraformStartApiIntegrationApplyBase):
    terraform_application = "lambda-auth-openapi"

    def setUp(self):
        self.url = "http://127.0.0.1:{}".format(self.port)

    @parameterized.expand(
        [
            ("/hello", {"headers": {"myheader": "123"}}),
            ("/hello-request", {"headers": {"myheader": "123"}, "params": {"mystring": "456"}}),
        ]
    )
    def test_successful_request(self, endpoint, params):
        response = requests.get(self.url + endpoint, timeout=300, **params)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"message": "from authorizer"})

    @parameterized.expand(
        [
            ("/hello", {"headers": {"missin": "123"}}),
            ("/hello-request", {"headers": {"notcorrect": "123"}, "params": {"abcde": "456"}}),
        ]
    )
    def test_missing_identity_sources(self, endpoint, params):
        response = requests.get(self.url + endpoint, timeout=300, **params)

        self.assertEqual(response.status_code, 401)
