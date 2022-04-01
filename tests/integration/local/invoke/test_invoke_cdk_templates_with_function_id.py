import json
import shutil
from pathlib import Path

import docker
import pytest
from docker.errors import APIError
from parameterized import parameterized

from samcli import __version__ as version
from samcli.local.docker.lambda_image import RAPID_IMAGE_TAG_PREFIX
from tests.integration.local.invoke.invoke_integ_base import InvokeIntegBase
from samcli.lib.utils.architecture import X86_64


class TestCDKSynthesizedTemplatesFunctionIdentifies(InvokeIntegBase):

    template = Path("cdk/cdk_function_id_template.yaml")

    @parameterized.expand(
        [
            ("StandardZipFunctionWithFunctionName", "ThisIsHelloWorldFunction", "LambdaWithFunctionName"),
        ]
    )
    @pytest.mark.flaky(reruns=3)
    def test_invoke_function_with_function_id(self, logical_id, function_name, function_id):
        self.teardown_function_name = logical_id
        function_identifiers = [function_name, logical_id, function_id]
        for identifier in function_identifiers:
            local_invoke_command_list = self.get_command_list(
                function_to_invoke=identifier, template_path=self.template_path
            )
            stdout, _, return_code = self.run_command(local_invoke_command_list)

            # Get the response without the sam-cli prompts that proceed it
            response = json.loads(stdout.decode("utf-8").split("\n")[0])
            expected_response = json.loads('{"statusCode":200,"body":"{\\"message\\":\\"%s\\"}"}' % logical_id)

            self.assertEqual(return_code, 0)
            self.assertEqual(response, expected_response)


class TestCDKSynthesizedTemplatesNestedFunctionIdentifies(InvokeIntegBase):

    template = Path("cdk/nested_templates/cdk_function_id_parent_template.yaml")

    @parameterized.expand([("LambdaWithUniqueFunctionName", "StandardZipFunctionWithFunctionUniqueName")])
    @pytest.mark.flaky(reruns=0)
    def test_invoke_function_with_unique_function_id(self, function_id_part, logical_id):
        self.teardown_function_name = [logical_id]
        local_invoke_command_list = self.get_command_list(
            function_to_invoke=function_id_part, template_path=self.template_path
        )
        stdout, _, return_code = self.run_command(local_invoke_command_list)

        # Get the response without the sam-cli prompts that proceed it
        response = json.loads(stdout.decode("utf-8").split("\n")[0])
        expected_response = json.loads('{"statusCode":200,"body":"{\\"message\\":\\"%s\\"}"}' % logical_id)

        self.assertEqual(return_code, 0)
        self.assertEqual(response, expected_response)

    @parameterized.expand(
        [("LambdaWithFunctionName", "StandardZipFunctionWithFunctionNameA", "StandardZipFunctionWithFunctionNameB")]
    )
    @pytest.mark.flaky(reruns=0)
    def test_invoke_function_with_duplicated_function_id(
        self, duplicated_function_id, expected_logical_id, not_invoked_logical_id
    ):
        self.teardown_function_name = [expected_logical_id, not_invoked_logical_id]
        local_invoke_command_list = self.get_command_list(
            function_to_invoke=duplicated_function_id, template_path=self.template_path
        )
        stdout, _, return_code = self.run_command(local_invoke_command_list)

        # Get the response without the sam-cli prompts that proceed it
        response = json.loads(stdout.decode("utf-8").split("\n")[0])
        expected_response = json.loads('{"statusCode":200,"body":"{\\"message\\":\\"%s\\"}"}' % expected_logical_id)

        self.assertEqual(return_code, 0)
        self.assertEqual(response, expected_response)
