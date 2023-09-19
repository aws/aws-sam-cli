from pathlib import Path
import shutil
import tempfile
import os

from unittest import skip
from samcli.lib.utils import osutils
from tests.integration.local.invoke.invoke_integ_base import InvokeIntegBase


@skip("Skipping build in source tests until feature can be enabled")
class TestInvokeBuildInSourceSymlinkedModules(InvokeIntegBase):
    def setUp(self):
        self.project_folder_path = Path(self.test_data_path, "invoke", "build-in-source")
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

    def _validate_modules_linked(self):
        node_modules = Path(self.build_dir, "PrintLocalDep", "node_modules")
        local_dep = Path(node_modules, "local-dep")

        # node modules folder should be a symlink
        self.assertEqual(os.path.islink(node_modules), True)

        # local-deps folder should not if links were installed
        self.assertEqual(os.path.islink(local_dep), False)

    def test_successful_invoke(self):
        build_command = self.get_build_command_list(template_path=self.template_path, build_dir=self.build_dir)
        print(build_command)
        _, _, exit_code = self.run_command(build_command)

        self.assertEqual(exit_code, 0)
        self._validate_modules_linked()

        invoke_command = self.get_command_list(
            template_path=self.built_template_path, function_to_invoke="PrintLocalDep"
        )
        stdout, _, exit_code = self.run_command(invoke_command)

        self.assertEqual(exit_code, 0)
        self.assertEqual(stdout.decode("utf-8"), "123")
