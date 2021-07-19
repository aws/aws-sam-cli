import os
import pathlib
import re
import shutil
import logging

from subprocess import Popen, PIPE, TimeoutExpired
import tempfile

from unittest import skipIf
from parameterized import parameterized, param

from samcli.lib.utils.hash import dir_checksum, file_checksum
from samcli.lib.warnings.sam_cli_warning import CodeDeployWarning
from .package_integ_base import CdkPackageIntegPythonBase
from tests.testing_utils import RUNNING_ON_CI, RUNNING_TEST_FOR_MASTER_ON_CI, RUN_BY_CANARY, run_command

# Package tests require credentials and CI/CD will only add credentials to the env if the PR is from the same repo.
# This is to restrict package tests to run outside of CI/CD, when the branch is not master and tests are not run by Canary.
SKIP_PACKAGE_TESTS = RUNNING_ON_CI and RUNNING_TEST_FOR_MASTER_ON_CI and not RUN_BY_CANARY
TIMEOUT = 300
LOG = logging.getLogger(__name__)


class TestPackageCdk(CdkPackageIntegPythonBase):

    @parameterized.expand(
        [
            "aws-lambda-function",
            "aws-lambda-layer",
        ]
    )
    def test_package_barebones(self, cdk_app_loc):
        test_data_path = self.test_data_path.joinpath("cdk", "python", cdk_app_loc)
        shutil.copytree(test_data_path, self.working_dir, dirs_exist_ok=True)
        self._install_deps()
        command_list = self.get_command_list(
            s3_bucket=self.s3_bucket.name,
            cdk_app=f"{self.venv_python} app.py",
        )
        LOG.debug("command list: %s", command_list)
        process_execute = run_command(command_list, cwd=self.working_dir)

        self.assertEqual(process_execute.process.returncode, 0)
        self.assertIn(self.s3_bucket.name, process_execute.stdout.decode("utf-8"))

    @parameterized.expand(
        [
            "aws-lambda-function",
            "aws-lambda-layer",
        ]
    )
    def test_package_with_prefix(self, cdk_app_loc):
        test_data_path = self.test_data_path.joinpath("cdk", "python", cdk_app_loc)
        shutil.copytree(test_data_path, self.working_dir, dirs_exist_ok=True)
        self._install_deps()
        s3_prefix = "integ_test_prefix"
        command_list = self.get_command_list(
            s3_bucket=self.s3_bucket.name,
            s3_prefix=s3_prefix,
            cdk_app=f"{self.venv_python} app.py",
        )
        LOG.debug("command list: %s", command_list)
        process_execute = run_command(command_list, cwd=self.working_dir)

        self.assertEqual(process_execute.process.returncode, 0)
        self.assertIn(self.s3_bucket.name, process_execute.stdout.decode("utf-8"))
        self.assertIn(s3_prefix, process_execute.stdout.decode("utf-8"))

    @parameterized.expand(
        [
            "aws-lambda-function",
            "aws-lambda-layer",
        ]
    )
    def test_package_with_output_template_file(self, cdk_app_loc):
        test_data_path = self.test_data_path.joinpath("cdk", "python", cdk_app_loc)
        shutil.copytree(test_data_path, self.working_dir, dirs_exist_ok=True)
        self._install_deps()
        s3_prefix = "integ_test_prefix"

        with tempfile.NamedTemporaryFile(delete=False) as output_template:
            command_list = self.get_command_list(
                s3_bucket=self.s3_bucket.name,
                s3_prefix=s3_prefix,
                output_template_file=output_template.name,
                cdk_app=f"{self.venv_python} app.py",
            )
            LOG.debug("command list: %s", command_list)
            process_execute = run_command(command_list, cwd=self.working_dir)

            self.assertEqual(process_execute.process.returncode, 0)
            self.assertIn(
                bytes(
                    f"Successfully packaged artifacts and wrote output template to file {output_template.name}",
                    encoding="utf-8",
                ),
                process_execute.stdout
            )

    @parameterized.expand(
        [
            "aws-lambda-function",
            "aws-lambda-layer",
        ]
    )
    def test_package_with_json(self, cdk_app_loc):
        test_data_path = self.test_data_path.joinpath("cdk", "python", cdk_app_loc)
        shutil.copytree(test_data_path, self.working_dir, dirs_exist_ok=True)
        self._install_deps()
        s3_prefix = "integ_test_prefix"

        with tempfile.NamedTemporaryFile(delete=False) as output_template:
            command_list = self.get_command_list(
                s3_bucket=self.s3_bucket.name,
                s3_prefix=s3_prefix,
                output_template_file=output_template.name,
                use_json=True,
                cdk_app=f"{self.venv_python} app.py",
            )
            LOG.debug("command list: %s", command_list)
            process_execute = run_command(command_list, cwd=self.working_dir)

            self.assertEqual(process_execute.process.returncode, 0)
            self.assertIn(
                bytes(
                    f"Successfully packaged artifacts and wrote output template to file {output_template.name}",
                    encoding="utf-8",
                ),
                process_execute.stdout
            )

