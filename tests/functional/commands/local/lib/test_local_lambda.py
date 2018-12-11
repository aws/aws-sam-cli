"""
Function test for Local Lambda runner
"""

import os
import io
import json
import shutil
import logging

from samcli.commands.local.lib import provider
from samcli.commands.local.lib.local_lambda import LocalLambdaRunner
from samcli.local.lambdafn.runtime import LambdaRuntime
from samcli.local.docker.manager import ContainerManager
from samcli.local.layers.layer_downloader import LayerDownloader
from samcli.local.docker.lambda_image import LambdaImage

from tests.functional.function_code import nodejs_lambda, GET_ENV_VAR
from unittest import TestCase
from mock import Mock

logging.basicConfig(level=logging.INFO)


class TestFunctionalLocalLambda(TestCase):

    def setUp(self):
        self.code_abs_path = nodejs_lambda(GET_ENV_VAR)

        # Let's convert this absolute path to relative path. Let the parent be the CWD, and codeuri be the folder
        self.cwd = os.path.dirname(self.code_abs_path)
        self.code_uri = os.path.relpath(self.code_abs_path, self.cwd)  # Get relative path with respect to CWD

        self.function_name = "name"
        self.variables = {
            "var1": "defaultvalue1",
            "var2": "defaultvalue2"
        }

        self.env_var_overrides = {
            self.function_name: {
                "var1": "override_value1"
            }
        }

        # Override "var2" through the Shell environment
        os.environ["var2"] = "shell_env_value2"

        self.function = provider.Function(name=self.function_name, runtime="nodejs4.3", memory=256, timeout=5,
                                          handler="index.handler", codeuri=self.code_uri,
                                          environment={"Variables": self.variables},
                                          rolearn=None, layers=[])

        self.mock_function_provider = Mock()
        self.mock_function_provider.get.return_value = self.function

    def tearDown(self):

        del os.environ["var2"]
        shutil.rmtree(self.code_abs_path)

    def test_must_invoke(self):
        input_event = '"some data"'
        expected_env_vars = {
            "var1": "override_value1",
            "var2": "shell_env_value2"
        }

        manager = ContainerManager()
        layer_downloader = LayerDownloader("./", "./")
        lambda_image = LambdaImage(layer_downloader, False, False)
        local_runtime = LambdaRuntime(manager, lambda_image)
        runner = LocalLambdaRunner(local_runtime, self.mock_function_provider, self.cwd, self.env_var_overrides,
                                   debug_context=None)

        # Append the real AWS credentials to the expected values.
        creds = runner.get_aws_creds()
        # default value for creds is not configured by the test. But coming from a downstream class
        expected_env_vars["AWS_SECRET_ACCESS_KEY"] = creds.get("secret", "defaultsecret")
        expected_env_vars["AWS_ACCESS_KEY_ID"] = creds.get("key", "defaultkey")
        expected_env_vars["AWS_REGION"] = creds.get("region", "us-east-1")

        stdout_stream = io.BytesIO()
        stderr_stream = io.BytesIO()
        runner.invoke(self.function_name, input_event, stdout=stdout_stream, stderr=stderr_stream)

        # stderr is where the Lambda container runtime logs are available. It usually contains requestId, start time
        # etc. So it is non-zero in size
        self.assertGreater(len(stderr_stream.getvalue().strip()), 0, "stderr stream must contain data")

        # This should contain all the environment variables passed to the function
        actual_output = json.loads(stdout_stream.getvalue().strip().decode('utf-8'))

        for key, value in expected_env_vars.items():
            self.assertTrue(key in actual_output, "Key '{}' must be in function output".format(key))
            self.assertEquals(actual_output.get(key), value)
