import re

import os
from pathlib import Path
import uuid
import shutil
import tempfile

from tests.integration.deploy.deploy_integ_base import DeployIntegBase
from tests.testing_utils import get_sam_command


class ListIntegBase(DeployIntegBase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.cmd = cls.base_command()
        cls.list_test_data_path = Path(__file__).resolve().parents[1].joinpath("testdata", "list")

    def setUp(self):
        super().setUp()
        self.scratch_dir = str(Path(__file__).resolve().parent.joinpath(str(uuid.uuid4()).replace("-", "")[:10]))
        shutil.rmtree(self.scratch_dir, ignore_errors=True)
        os.mkdir(self.scratch_dir)
        self.working_dir = tempfile.mkdtemp(dir=self.scratch_dir)

    def tearDown(self):
        super().tearDown()
        self.working_dir and shutil.rmtree(self.working_dir, ignore_errors=True)
        self.scratch_dir and shutil.rmtree(self.scratch_dir, ignore_errors=True)
        self.cleanup_config()

    def cleanup_config(self):
        config_path = Path(self.list_test_data_path, "samconfig.toml")
        if os.path.exists(config_path):
            os.remove(config_path)

    @classmethod
    def base_command(cls):
        return get_sam_command()

    @staticmethod
    def _find_resource(resources, logical_id):
        for resource in resources:
            resource_logical_id = resource.get("LogicalResourceId", "")
            if resource_logical_id == logical_id or re.match(logical_id, resource_logical_id):
                return resource
        return None
