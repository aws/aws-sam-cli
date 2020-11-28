from pathlib import Path
import os

from unittest import skipIf
from parameterized import parameterized

from tests.integration.local.invoke.invoke_integ_base import InvokeIntegBase
from tests.testing_utils import RUNNING_ON_CI, RUN_BY_CANARY

SKIP_CREDENTIALS_TESTS = RUNNING_ON_CI and not RUN_BY_CANARY


@skipIf(SKIP_CREDENTIALS_TESTS, "Run credentials test only in Canary")
class TestWithCredentials(InvokeIntegBase):
    template = Path("credential_tests/template.yaml")

    @parameterized.expand(
        [
            "JavaStsExample",
            "PythonStsExample",
            "RubyStsExample",
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
        self.assertTrue(b"Build Succeeded" in stdout)
        self.assertEqual(returncode, 0)

        # then invoke using temp credentials
        process_env_vars = {
            **os.environ,
            "AWS_ACCESS_KEY": "$AWS_ACCESS_KEY",
            "AWS_SECRET_ACCESS_KEY": "$AWS_SECRET_ACCESS_KEY",
        }
        local_invoke_command_list = self.get_command_list(function_to_invoke=function_name)
        stdout, _, returncode = self.run_command(local_invoke_command_list, env=process_env_vars)
        self.assertEqual(returncode, 0)
        self.assertTrue(b'"statusCode":200' in stdout)
