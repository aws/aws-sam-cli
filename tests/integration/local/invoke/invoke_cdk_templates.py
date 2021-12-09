import json
import shutil
from pathlib import Path
from unittest import skipIf

import docker
import pytest
from docker.errors import APIError
from parameterized import parameterized
from timeit import default_timer as timer

from samcli import __version__ as version
from samcli.local.docker.lambda_image import RAPID_IMAGE_TAG_PREFIX
from samcli.lib.utils.architecture import X86_64
from tests.integration.local.invoke.invoke_integ_base import InvokeIntegBase
from tests.integration.local.invoke.test_integrations_cli import TestLayerVersionBase, SKIP_LAYERS_TESTS
from tests.testing_utils import IS_WINDOWS, RUNNING_ON_CI, CI_OVERRIDE


class TestCDKSynthesizedTemplate(InvokeIntegBase):
    template = Path("cdk/cdk_template.yaml")

    @pytest.mark.flaky(reruns=3)
    def test_invoke_returncode_is_zero(self):
        command_list = self.get_command_list(
            "helloworld-serverless-function", event_path=self.event_path, template_path=self.template_path
        )
        stdout, _, return_code = self.run_command(command_list)

        self.assertEqual(return_code, 0)

    @pytest.mark.flaky(reruns=3)
    def test_invoke_with_utf8_event(self):
        command_list = self.get_command_list(
            "helloworld-serverless-function", event_path=self.event_utf8_path, template_path=self.template_path
        )
        stdout, _, return_code = self.run_command(command_list)

        self.assertEqual(return_code, 0)

    @pytest.mark.flaky(reruns=3)
    def test_invoke_returns_expected_results(self):
        command_list = self.get_command_list(
            "helloworld-serverless-function", event_path=self.event_path, template_path=self.template_path
        )

        stdout, _, return_code = self.run_command(command_list)

        process_stdout = stdout.strip()
        self.assertEqual(process_stdout.decode("utf-8"), '"Hello world"')

    @pytest.mark.flaky(reruns=3)
    def test_invoke_with_timeout_set(self):
        command_list = self.get_command_list(
            "timeout-function", event_path=self.event_path, template_path=self.template_path
        )

        start = timer()

        stdout, _, return_code = self.run_command(command_list)

        end = timer()

        wall_clock_cli_duration = end - start

        process_stdout = stdout.strip()

        # validate the time of the cli (timeout is set to 5s)
        self.assertGreater(wall_clock_cli_duration, 5)
        self.assertLess(wall_clock_cli_duration, 20)

        self.assertEqual(return_code, 0)
        self.assertEqual(
            process_stdout.decode("utf-8"),
            "",
            msg="The return statement in the LambdaFunction " "should never return leading to an empty string",
        )

    @pytest.mark.flaky(reruns=3)
    def test_invoke_with_env_vars(self):
        command_list = self.get_command_list(
            "custom-env-vars-function", event_path=self.event_path, template_path=self.template_path
        )

        stdout, _, return_code = self.run_command(command_list)
        process_stdout = stdout.strip()

        self.assertEqual(process_stdout.decode("utf-8"), '"MyVar"')

    @pytest.mark.flaky(reruns=3)
    def test_invoke_when_function_writes_stdout(self):
        command_list = self.get_command_list(
            "write-to-stdout-function", event_path=self.event_path, template_path=self.template_path
        )

        stdout, _, return_code = self.run_command(command_list)

        process_stdout = stdout.strip()

        self.assertIn("wrote to stdout", process_stdout.decode("utf-8"))

    @pytest.mark.flaky(reruns=3)
    def test_invoke_returns_expected_result_when_no_event_given(self):
        command_list = self.get_command_list("echo-event-function", template_path=self.template_path)

        stdout, _, return_code = self.run_command(command_list)

        process_stdout = stdout.strip()

        self.assertEqual(return_code, 0)
        self.assertEqual("{}", process_stdout.decode("utf-8"))

    @pytest.mark.flaky(reruns=3)
    def test_invoke_with_parameters_overrides(self):
        command_list = self.get_command_list(
            "echo-env-with-parameters",
            event_path=self.event_path,
            parameter_overrides={"MyRuntimeVersion": "v0", "TimeOut": "100"},
            template_path=self.template_path,
        )

        stdout, _, return_code = self.run_command(command_list)
        process_stdout = stdout.strip()
        environ = json.loads(process_stdout.decode("utf-8"))

        self.assertIsNone(environ.get("TimeOut"))
        self.assertEqual(environ["MyRuntimeVersion"], "v0")


@skipIf(
    ((IS_WINDOWS and RUNNING_ON_CI) and not CI_OVERRIDE),
    "Skip build tests on windows when running in CI unless overridden",
)
class TestCDKSynthesizedTemplatesImageFunctions(InvokeIntegBase):

    template = Path("cdk/cdk_template_image_functions.yaml")
    functions = [
        "StandardFunctionConstructZipFunction",
        "StandardFunctionConstructImageFunction",
        "DockerImageFunctionConstruct",
    ]

    @classmethod
    def setUpClass(cls):
        # Run sam build first to build the image functions
        # We only need to create these images once
        # We remove them after they are no longer used
        super(TestCDKSynthesizedTemplatesImageFunctions, cls).setUpClass()
        build_command_list = super().get_build_command_list(cls, template_path=cls.template_path)
        super().run_command(cls, command_list=build_command_list)

    def tearDown(self) -> None:
        # Tear down a unique image resource after it is finished being used
        docker_client = docker.from_env()
        try:
            to_remove = self.teardown_function_name
            docker_client.api.remove_image(f"{to_remove.lower()}")
            docker_client.api.remove_image(f"{to_remove.lower()}:{RAPID_IMAGE_TAG_PREFIX}-{version}-{X86_64}")
        except (APIError, AttributeError):
            pass

        try:
            # We don't actually use the build dir so we don't care if it's removed before another process finishes
            shutil.rmtree(str(Path().joinpath(".aws-sam")))
        except FileNotFoundError:
            pass

    @parameterized.expand(functions)
    @pytest.mark.flaky(reruns=3)
    def test_build_and_invoke_image_function(self, function_name):
        # Set the function name to be removed during teardown
        self.teardown_function_name = function_name
        local_invoke_command_list = self.get_command_list(
            function_to_invoke=function_name, template_path=self.template_path
        )
        stdout, _, return_code = self.run_command(local_invoke_command_list)

        # Get the response without the sam-cli prompts that proceed it
        response = json.loads(stdout.decode("utf-8").split("\n")[0])
        expected_response = json.loads('{"statusCode":200,"body":"{\\"message\\":\\"hello world\\"}"}')

        self.assertEqual(return_code, 0)
        self.assertEqual(response, expected_response)

    def test_invoke_with_utf8_event(self):
        command_list = self.get_command_list(
            "StandardFunctionConstructZipFunction", template_path=self.template_path, event_path=self.event_utf8_path
        )
        stdout, _, return_code = self.run_command(command_list)
        self.assertEqual(return_code, 0)


class TestRuntimeFunctionConstructs(InvokeIntegBase):
    """
    Runtime specific functions are bundled and the synthesized
    templated points to the bundled asset, not the source code.

    FunctionBundledAssets is not a runtime specific function, but
    uses a CDK property that bundles the function.

    It looks like this:

    new lambda.Function(this, 'FunctionBundledAssets', {
      code: lambda.Code.fromAsset('./my_function', {
        bundling: {
          image: lambda.Runtime.PYTHON_3_9.bundlingImage,
          command: [
            'bash', '-c',
            'pip install -r requirements.txt -t /asset-output && cp -au . /asset-output'
          ],
        },
      }),
      runtime: lambda.Runtime.PYTHON_3_9,
      handler: 'app.lambda_handler',
    });
    """

    template = Path("cdk/runtime_function_constructs.yaml")

    @parameterized.expand(["NodeJsFunction", "PythonFunction", "GoFunction", "FunctionBundledAssets"])
    def test_runtime_function_construct(self, function_name):
        local_invoke_command_list = self.get_command_list(
            function_to_invoke=function_name, template_path=self.template_path
        )
        stdout, _, return_code = self.run_command(local_invoke_command_list)

        # Get the response without the sam-cli prompts that proceed it
        response = stdout.decode("utf-8").split("\n")[0]
        expected_response = f'"Hello from {function_name}!"'

        self.assertEqual(return_code, 0)
        self.assertEqual(response, expected_response)


@skipIf(SKIP_LAYERS_TESTS, "Skip layers tests in Appveyor only")
class TestCDKLayerVersion(TestLayerVersionBase):
    # region = "us-west-2"
    # layer_utils = LayerUtils(region=region)
    template = Path("cdk/cdk_layers_template.yaml")

    def test_reference_of_layer_version(self):
        function_identifier = "sample-function"
        command_list = self.get_command_list(
            function_identifier,
            template_path=self.template_path,
            no_event=True,
            region=self.region,
            layer_cache=str(self.layer_cache),
            parameter_overrides=self.layer_utils.parameters_overrides,
        )

        stdout, _, return_code = self.run_command(command_list)

        process_stdout = stdout.strip()

        expected_output = '"This is a Layer Ping from simple_python"'

        self.assertEqual(process_stdout.decode("utf-8"), expected_output)
