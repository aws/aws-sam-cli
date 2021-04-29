import os
import shutil
from pathlib import Path

from samcli.lib.iac.interface import Project, LookupPath, LookupPathType
from unittest import TestCase
from unittest.mock import Mock

from samcli.lib.iac.cdk.plugin import CdkPlugin

from tests.unit.lib.iac.cdk.helper import read_json_file

CLOUD_ASSEMBLY_DIR = os.path.join(os.path.dirname(__file__), "test_data", "cdk.out")


class TestCdkPlugin(TestCase):
    def setUp(self) -> None:
        context = Mock()
        context.command_params = {"cdk_app": CLOUD_ASSEMBLY_DIR}
        self.plugin = CdkPlugin(context)
        self.project = self.plugin.get_project([LookupPath(os.path.dirname(__file__), LookupPathType.SOURCE)])

    def test_get_project(self):
        self.assertIsInstance(self.project, Project)
        self.assertEqual(len(self.project.stacks), 2)
        root_stack = self.project.stacks[0]
        self.assertEqual(len(root_stack.assets), 5)

    def test_write_project(self):
        filenames = [
            "root-stack.template.json",
            "rootstacknestedstackACD02B51.nested.template.json",
            "rootstacknestedstacknestednestedstackE7ADAD2C.nested.template.json",
            "Stack2.template.json",
        ]
        build_dir = Path(CLOUD_ASSEMBLY_DIR, ".build")
        build_dir_path = str(build_dir)
        build_dir.mkdir(exist_ok=True)
        self.plugin.write_project(self.project, build_dir_path)
        self.assertTrue(os.path.isfile(os.path.join(build_dir_path, "manifest.json")))
        self.assertTrue(os.path.isfile(os.path.join(build_dir_path, "tree.json")))
        self.assertTrue(os.path.isfile(os.path.join(build_dir_path, "cdk.out")))
        for filename in filenames:
            self.assertTrue(os.path.isfile(os.path.join(build_dir_path, filename)))
            expected = read_json_file(
                os.path.join(CLOUD_ASSEMBLY_DIR, filename.replace(".template.json", ".template.normalized.json")),
                "<current_dir_path>/",
                f"{str(CLOUD_ASSEMBLY_DIR)}{os.path.sep}",
            )
            actual = read_json_file(os.path.join(build_dir_path, filename))
            self.assertEqual(actual, expected)

        shutil.rmtree(build_dir)
