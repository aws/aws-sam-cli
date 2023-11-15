from pathlib import Path
import shutil
import tempfile
import os

from samcli.lib.utils import osutils
from tests.integration.local.invoke.invoke_integ_base import InvokeIntegBase


class BuildInSourceInvokeBase(InvokeIntegBase):
    project_test_folder: str

    def setUp(self):
        self.project_folder_path = Path(self.test_data_path, "invoke", self.project_test_folder)
        self.test_project_folder = tempfile.mkdtemp()
        self.build_dir = Path(self.test_project_folder, ".aws-sam", "build")

        osutils.copytree(self.project_folder_path, self.test_project_folder)

        self.template_path = Path(self.test_project_folder, "template.yaml")
        self.built_template_path = Path(self.build_dir, "template.yaml")

    def tearDown(self):
        try:
            shutil.rmtree(self.test_project_folder, ignore_errors=True)
        except:
            pass


class TestInvokeBuildInSourceSymlinkedModules(BuildInSourceInvokeBase):
    project_test_folder = "build-in-source"

    def _validate_modules_linked(self):
        node_modules = Path(self.build_dir, "PrintLocalDep", "node_modules")
        local_dep = Path(node_modules, "local-dep")

        # node modules folder should be a symlink
        self.assertEqual(os.path.islink(node_modules), True)

        # local-deps folder should not if links were installed
        self.assertEqual(os.path.islink(local_dep), False)

    def test_successful_invoke(self):
        build_command = self.get_build_command_list(
            template_path=self.template_path, build_dir=self.build_dir, build_in_source=True
        )
        _, _, exit_code = self.run_command(build_command)

        self.assertEqual(exit_code, 0)
        self._validate_modules_linked()

        invoke_command = self.get_command_list(
            template_path=self.built_template_path, function_to_invoke="PrintLocalDep"
        )
        stdout, _, exit_code = self.run_command(invoke_command)

        self.assertEqual(exit_code, 0)
        self.assertEqual(stdout.decode("utf-8"), "123")


class TestInvokeBuildInSourceSymlinkedLayers(BuildInSourceInvokeBase):
    project_test_folder = str(Path("build-in-source", "layer_symlink"))

    def test_successful_invoke(self):
        build_command = self.get_build_command_list(
            template_path=self.template_path, build_dir=self.build_dir, build_in_source=True
        )

        _, _, exit_code = self.run_command(build_command, cwd=self.test_project_folder)

        self.assertEqual(exit_code, 0)

        # check if layers is symlinked
        layer_artifact_node_folder = Path(self.build_dir, "MyLayer", "nodejs", "node_modules")
        self.assertEqual(os.path.islink(layer_artifact_node_folder), True)

        invoke_command = self.get_command_list(
            template_path=self.built_template_path, function_to_invoke="HelloWorldFunction"
        )
        stdout, _, exit_code = self.run_command(invoke_command, cwd=self.test_project_folder)

        self.assertEqual(exit_code, 0)
        self.assertEqual(stdout.decode("utf-8"), '{"statusCode": 200, "body": "foo bar"}')
