"""Integration tests for sam local start-api with durable functions."""

import shutil
import pytest
import requests
from pathlib import Path

from tests.integration.local.start_api.start_api_integ_base import StartApiIntegBaseClass
from tests.integration.durable_integ_base import DurableIntegBase


class TestStartApiDurable(DurableIntegBase, StartApiIntegBaseClass):
    template_path = "/testdata/durable/template.yaml"
    container_host_interface = "0.0.0.0"

    @classmethod
    def setUpClass(cls):
        cls.test_data_path = Path(cls.integration_dir, "testdata")
        cls.template_path = str(Path(cls.test_data_path, "durable", "template.yaml"))
        cls.build_durable_functions()
        cls.template_path = "/" + str(cls.built_template_path.relative_to(cls.integration_dir))
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        build_dir = Path(cls.test_data_path, "durable", ".aws-sam")
        shutil.rmtree(build_dir, ignore_errors=True)
        super().tearDownClass()

    def setUp(self):
        self.url = f"http://127.0.0.1:{self.port}"

    @pytest.mark.timeout(timeout=600, method="thread")
    def test_get_hello_world_durable_function(self):
        """Test GET request to durable function endpoint."""
        response = requests.get(self.url + "/hello", timeout=300)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"message": "Hello, World!"})
