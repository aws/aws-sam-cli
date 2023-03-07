import json
import tempfile
import shutil
import os
from time import time

from unittest.mock import MagicMock, patch
from unittest import TestCase
from pathlib import Path
from samcli.commands.init.init_templates import InitTemplates

from samcli.commands.init.interactive_init_flow import do_interactive


class TestInteractiveFlow(TestCase):
    def setUp(self):
        self.prompt_patch = patch("samcli.commands.init.interactive_init_flow.click.prompt")
        self.prompt_mock = self.prompt_patch.start()
        self.addCleanup(self.prompt_patch.stop)

        self.confirm_patch = patch("samcli.commands.init.interactive_init_flow.click.confirm")
        self.confirm_mock = self.confirm_patch.start()
        self.addCleanup(self.confirm_patch.stop)

        self.output_dir = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.output_dir)

    @patch("samcli.commands.init.init_templates.requests")
    @patch("samcli.commands.init.init_templates.GitRepo")
    def test_unknown_runtime(self, git_repo_mock, requests_mock):
        testdata_path = (
            Path(__file__).resolve().parents[3].joinpath("functional", "testdata", "init", "unknown_runtime")
        )
        manifest_path = testdata_path.joinpath("manifest-v2.json")

        repo_mock = MagicMock()
        git_repo_mock.return_value = repo_mock
        repo_mock.local_path = testdata_path

        requests_mock.get.return_value.text = manifest_path.read_text()

        self.prompt_mock.side_effect = [
            "1",  # Which template source -> AWS
            "unknown_runtime_app",  # Project name
        ]
        self.confirm_mock.side_effect = [False]
        do_interactive(
            location=None,
            pt_explicit=False,
            package_type=None,
            runtime=None,
            architecture=None,
            base_image=None,
            dependency_manager=None,
            output_dir=str(self.output_dir),
            name=None,
            app_template=None,
            no_input=False,
            tracing=False,
            application_insights=False,
        )
        output_files = list(self.output_dir.rglob("*"))
        self.assertEqual(len(output_files), 9)
        unique_test_file_path = self.output_dir / "unknown_runtime_app" / "unique_test_file.txt"
        self.assertIn(unique_test_file_path, output_files)
