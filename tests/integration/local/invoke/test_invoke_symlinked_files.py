import os
from pathlib import Path
import shutil
import tempfile
from samcli.lib.utils import osutils
from tests.integration.local.invoke.invoke_integ_base import InvokeIntegBase


class TestInvokeContainerMountsResolvedLinks(InvokeIntegBase):
    def setUp(self):
        self.project_folder_path = Path(self.test_data_path, "invoke", "symlinked")
        self.test_project_folder = tempfile.mkdtemp()

        osutils.copytree(self.project_folder_path, self.test_project_folder)

        self.source_file_path = Path(self.test_project_folder, "source-file.txt")
        self.dest_file_path = Path(self.test_project_folder, "src", "linked-file.txt")

        os.symlink(self.source_file_path.absolute(), self.dest_file_path.absolute())

        self.template_path = Path(self.test_project_folder, "template.yaml")

    def tearDown(self):
        try:
            shutil.rmtree(self.test_project_folder)
        except: pass

    def test_successful_invoke(self):
        command = self.get_command_list(template_path=self.template_path, function_to_invoke="PrintLinkedFile")
        stdout, _, exit_code = self.run_command(command)

        self.assertEqual(exit_code, 0)
        self.assertEqual(stdout.decode("utf-8"), '"cats"')
