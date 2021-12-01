import json
from pathlib import Path
from unittest import skipIf

import docker
import pytest
from docker.errors import APIError
from parameterized import parameterized

from samcli import __version__ as version
from samcli.local.docker.lambda_image import RAPID_IMAGE_TAG_PREFIX
from tests.integration.local.invoke.invoke_integ_base import InvokeIntegBase
from samcli.lib.utils.architecture import X86_64
from tests.testing_utils import IS_WINDOWS, RUNNING_ON_CI, CI_OVERRIDE


@skipIf(
    ((IS_WINDOWS and RUNNING_ON_CI) and not CI_OVERRIDE),
    "Skip build tests on windows when running in CI unless overridden",
)
class TestCDKSynthesizedTemplatesFunctions(InvokeIntegBase):

    template = Path("cdk/cdk_template.yaml")
    functions = [
        "StandardFunctionConstructZipFunction",
        "StandardFunctionConstructImageFunction",
        "DockerImageFunctionConstruct",
    ]

    @classmethod
    def setUpClass(cls):
        # Run sam build first to build the image functions
        # We only need to create these images once, and we can reuse the for
        # all tests since they don't change. Then we remove them after all tests are run.
        super(TestCDKSynthesizedTemplatesFunctions, cls).setUpClass()
        build_command_list = super().get_build_command_list(cls, template_path=cls.template_path)
        super().run_command(cls, command_list=build_command_list)

    @classmethod
    def tearDownClass(cls) -> None:
        # Remove images
        docker_client = docker.from_env()
        for function in cls.functions:
            try:
                docker_client.api.remove_image(f"{function.lower()}")
                docker_client.api.remove_image(f"{function.lower()}:{RAPID_IMAGE_TAG_PREFIX}-{version}-{X86_64}")
            except APIError:
                pass

    @parameterized.expand(functions)
    @pytest.mark.flaky(reruns=3)
    def test_build_and_invoke_image_function(self, function_name):
        local_invoke_command_list = self.get_command_list(
            function_to_invoke=function_name, template_path=self.template_path
        )
        stdout, _, return_code = self.run_command(local_invoke_command_list)

        # Get the response without the sam-cli prompts that proceed it
        response = json.loads(stdout.decode("utf-8").split("\n")[0])
        expected_response = json.loads('{"statusCode":200,"body":"{\\"message\\":\\"hello world\\"}"}')

        self.assertEqual(return_code, 0)
        self.assertEqual(response, expected_response)

    @parameterized.expand(functions)
    @pytest.mark.flaky(reruns=3)
    def test_invoke_with_utf8_event(self, function_name):
        command_list = self.get_command_list(
            function_name, template_path=self.template_path, event_path=self.event_utf8_path
        )
        stdout, _, return_code = self.run_command(command_list)
        self.assertEqual(return_code, 0)
