import shutil
import os
from pathlib import Path
from typing import Optional
from unittest import skipIf
from http.client import HTTPConnection

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
