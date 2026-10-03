"""
Base class for generate openapi integration tests
"""

import os
import uuid
import shutil
import tempfile
from pathlib import Path
from unittest import TestCase
from tests.testing_utils import get_sam_command, run_command


class GenerateOpenApiIntegBase(TestCase):
    template = "template.yaml"

    @classmethod
    def setUpClass(cls):
        cls.cmd = get_sam_command()
        integration_dir = Path(__file__).resolve().parents[1]
        cls.test_data_path = str(Path(integration_dir, "testdata", "generate", "openapi"))

    def setUp(self):
        self.scratch_dir = str(Path(__file__).resolve().parent.joinpath("tmp", str(uuid.uuid4()).replace("-", "")[:10]))
        shutil.rmtree(self.scratch_dir, ignore_errors=True)
        os.makedirs(self.scratch_dir)

        self.working_dir = tempfile.mkdtemp(dir=self.scratch_dir)
        self.output_file_path = Path(self.working_dir, "openapi.yaml")

    def tearDown(self):
        self.working_dir and shutil.rmtree(self.working_dir, ignore_errors=True)
        self.scratch_dir and shutil.rmtree(self.scratch_dir, ignore_errors=True)

    def get_command_list(self, template_path, api_logical_id=None, output_file=None, format="yaml"):
        """Build command list for generate openapi"""
        command_list = [self.cmd, "generate", "openapi"]

        if template_path:
            command_list += ["-t", template_path]

        if api_logical_id:
            command_list += ["--api-logical-id", api_logical_id]

        if output_file:
            command_list += ["-o", output_file]

        if format:
            command_list += ["--format", format]

        return command_list
