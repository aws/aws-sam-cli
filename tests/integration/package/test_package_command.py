from subprocess import Popen, PIPE

from unittest import skipIf

from .package_integ_base import PackageIntegBase
from tests.testing_utils import RUNNING_ON_CI, RUNNING_TEST_FOR_MASTER_ON_CI

# Package tests require credentials and CI/CD will only add credentials to the env if the PR is from the same repo.
# This is to restrict package tests to run outside of CI/CD and when the branch is not master.
SKIP_PACKAGE_TESTS = RUNNING_ON_CI and RUNNING_TEST_FOR_MASTER_ON_CI


@skipIf(SKIP_PACKAGE_TESTS, "Skip package tests in CI/CD only")
class TestPackage(PackageIntegBase):
    def setUp(self):
        super(TestPackage, self).setUp()

    def tearDown(self):
        super(TestPackage, self).tearDown()

    def test_package_barebones(self):
        template_path = self.test_data_path.joinpath("template.yaml")
        command_list = self.get_command_list(s3_bucket=self.s3_bucket.name, template_file=template_path)

        process = Popen(command_list, stdout=PIPE)
        process.wait()
        process_stdout = b"".join(process.stdout.readlines()).strip()

        self.assertIn("CodeUri: s3://", process_stdout.decode("utf-8"))
