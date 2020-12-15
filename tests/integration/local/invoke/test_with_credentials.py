from pathlib import Path
from unittest import skipIf

from parameterized import parameterized

from tests.integration.local.invoke.invoke_integ_base import InvokeIntegBase
from tests.testing_utils import RUNNING_ON_CI, RUN_BY_CANARY, IS_WINDOWS

SKIP_CREDENTIALS_TESTS = IS_WINDOWS or RUNNING_ON_CI or not RUN_BY_CANARY


class CredentialsTestBase(InvokeIntegBase):
    def invoke_functions_and_validate(self, function_name):
        local_invoke_command_list = self.get_command_list(function_to_invoke=function_name)
        stdout, _, returncode = self.run_command(local_invoke_command_list)
        self.assertEqual(returncode, 0)
        self.assertTrue((b'"statusCode": 200' in stdout) or (b'"statusCode":200' in stdout))


@skipIf(SKIP_CREDENTIALS_TESTS, "Run credentials test only in Canary")
class TestWithCredentials(CredentialsTestBase):
    template = Path("credential_tests/inprocess/template.yaml")

    @parameterized.expand(
        [
            "DotnetStsExample",
            "GoStsExample",
        ]
    )
    def test_build_and_invoke_functions(self, function_name):
        """
        This method will first build functions (which contains a credentials call)
        Then invoke each of them with passing AWS session env variables
        """
        # first build application
        build_command_list = self.get_build_command_list(template_path=self.template_path, cached=True)
        stdout, _, returncode = self.run_command(build_command_list)
        self.assertEqual(returncode, 0)

        self.invoke_functions_and_validate(function_name)


@skipIf(SKIP_CREDENTIALS_TESTS, "Run credentials test only in Canary")
class TestWithCredentialsBuildUsingContainer(CredentialsTestBase):
    template = Path("credential_tests/incontainer/template.yaml")

    @parameterized.expand(
        [
            "JavaStsExample",
            "PythonStsExample",
            "RubyStsExample",
            "NodeStsExample",
        ]
    )
    def test_build_and_invoke_functions(self, function_name):
        """
        This method will first build functions (which contains a credentials call)
        Then invoke each of them with passing AWS session env variables
        """
        # first build application
        build_command_list = self.get_build_command_list(
            template_path=self.template_path, cached=True, use_container=True
        )
        stdout, _, returncode = self.run_command(build_command_list)
        self.assertEqual(returncode, 0)

        self.invoke_functions_and_validate(function_name)
