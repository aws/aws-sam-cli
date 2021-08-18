from unittest import skipIf

from .build_integ_base import CdkBuildIntegPythonBase, CdkBuildIntegNodejsBase
from distutils.dir_util import copy_tree
from pathlib import Path
from tests.testing_utils import run_command, RUN_BY_CANARY
import logging
import requests
import os

LOG = logging.getLogger(__name__)


@skipIf(
    not RUN_BY_CANARY,
    "Skip build tests that are not running on canaries",
)
class TestBuildWithCDKPluginNestedStacks(CdkBuildIntegPythonBase):
    def test_cdk_nested_build(self):
        project_name = "cdk-example-multiple-stacks-01"
        test_data_path = os.path.join(self.test_data_path, "CDK", project_name)
        copy_tree(test_data_path, self.working_dir)
        self.cdk_python_env.install_dependencies(os.path.join(self.working_dir, "requirements.txt"))
        self.verify_build_success(self.working_dir)
        self.verify_included_expected_project_manifest()

        # Verify invoke after build
        body = f'{{"message":"hello world from Docker"}}'
        expected = {"body": body, "statusCode": 200}
        self.verify_invoke_built_function("root-stack/container-function", expected, self.working_dir)
        expected = get_expected_response(message="hello world")
        self.verify_invoke_built_function("root-stack/nested-stack/cdk-wing-test-lambda", expected, self.working_dir)
        expected = get_expected_response(message="hello world 2!")
        self.verify_invoke_built_function("Stack2/cdk-wing-test-lambda", expected, self.working_dir)
        expected = get_expected_response(message="hello world 3!")
        self.verify_invoke_built_function(
            "root-stack/nested-stack/nested-nested-stack/cdk-wing-test-lambda", expected, self.working_dir
        )


@skipIf(
    not RUN_BY_CANARY,
    "Skip build tests that are not running on canaries",
)
class TestBuildWithCDKPluginWithApiGateway(CdkBuildIntegNodejsBase):
    def test_cdk_apigateway(self):
        project_name = "cdk-example-rest-api-gateway"
        test_data_path = os.path.join(self.test_data_path, "CDK", project_name)
        copy_tree(test_data_path, self.working_dir)
        self.verify_build_success(self.working_dir)
        self.verify_included_expected_project_manifest()
        body = f'{{"message":"Lambda was invoked successfully from APIGW."}}'
        expected = {"body": body, "statusCode": 200}
        self.verify_invoke_built_function(
            "CdkExampleRestApiGatewayStack/APIGWLambdaFunction", expected, self.working_dir
        )


@skipIf(
    not RUN_BY_CANARY,
    "Skip build tests that are not running on canaries",
)
class TestBuildWithCDKPluginWithApiCorsLambda(CdkBuildIntegPythonBase):
    def test_cdk_api_cors_lambda(self):
        project_name = "api-cors-lambda"
        test_data_path = os.path.join(self.test_data_path, "CDK", project_name)
        copy_tree(test_data_path, self.working_dir)
        self.cdk_python_env.install_dependencies(os.path.join(self.working_dir, "requirements.txt"))
        self.verify_build_success(self.working_dir)
        self.verify_included_expected_project_manifest()
        expected = {"body": "Lambda was invoked successfully.", "statusCode": 200}
        self.verify_invoke_built_function("ApiCorsLambdaStack/ApiCorsLambda", expected, self.working_dir)


@skipIf(
    not RUN_BY_CANARY,
    "Skip build tests that are not running on canaries",
)
class TestBuildWithCDKLayer(CdkBuildIntegPythonBase):
    def test_cdk_layer(self):
        project_name = "cdk-example-layer"
        test_data_path = os.path.join(self.test_data_path, "CDK", project_name)
        copy_tree(test_data_path, self.working_dir)
        self.cdk_python_env.install_dependencies(os.path.join(self.working_dir, "requirements.txt"))
        cmd_list = self.get_command_list(use_container=True)
        self.verify_build_success(self.working_dir, cmd_list)
        self.verify_included_expected_project_manifest()
        expected = get_expected_response(message="hello world")
        self.verify_invoke_built_function("CdkExampleLayerStack/lambda-function", expected, self.working_dir)


@skipIf(
    not RUN_BY_CANARY,
    "Skip build tests that are not running on canaries",
)
class TestBuildWithCDKVariousOptions(CdkBuildIntegPythonBase):
    project_name = "api-cors-lambda"

    def test_cdk_build_with_use_container(self):
        cmd_list = self.get_command_list(use_container=True)
        self._verify_build(self.project_name, cmd_list)

    def test_cdk_build_with_cache(self):
        cache_dir = Path(self.working_dir, ".aws-sam", "cache")
        cmd_list = self.get_command_list(cached=True, cache_dir=str(cache_dir))
        self._verify_build(self.project_name, cmd_list)
        self._verify_cached_artifact(cache_dir)
        self._verify_build(self.project_name, cmd_list)

    def test_cdk_build_with_parallel(self):
        cmd_list = self.get_command_list(parallel=True)
        self._verify_build(self.project_name, cmd_list)

    def test_cdk_build_with_correct_project_type(self):
        cmd_list = self.get_command_list(project_type="CDK")
        self._verify_build(self.project_name, cmd_list)

    def test_cdk_build_with_incorrect_project_type(self):
        cmd_list = self.get_command_list(project_type="CFN")
        self._verify_build_failed(self.project_name, cmd_list)

    def test_cdk_build_with_cdk_context(self):
        cmd_options = ["--cdk-context", "layer_id=another_layer_id", "--cdk-context", "another_handler=app.handler2"]
        cmd_list = self.get_command_list(project_type="CDK")
        cmd_list += cmd_options
        self._verify_build(self.project_name, cmd_list)

    def _verify_build(self, project_name, cmd_list):
        test_data_path = os.path.join(self.test_data_path, "CDK", project_name)
        copy_tree(test_data_path, self.working_dir)
        self.cdk_python_env.install_dependencies(os.path.join(self.working_dir, "requirements.txt"))
        self.verify_build_success(self.working_dir, cmd_list)
        self.verify_included_expected_project_manifest()
        expected = {"body": "Lambda was invoked successfully.", "statusCode": 200}
        self.verify_invoke_built_function("ApiCorsLambdaStack/ApiCorsLambda", expected, self.working_dir)

    def _verify_cached_artifact(self, cache_dir):
        self.assertTrue(cache_dir.exists(), "Cache directory should be created")

    def _verify_build_failed(self, project_name, cmd=None):
        test_data_path = os.path.join(self.test_data_path, "CDK", project_name)
        copy_tree(test_data_path, self.working_dir)
        self.cdk_python_env.install_dependencies(os.path.join(self.working_dir, "requirements.txt"))
        if cmd:
            cmd_list = cmd
        else:
            cmd_list = self.get_command_list()
        LOG.info("Running Command: {}".format(cmd_list))
        LOG.info(cmd_list)
        process_execute = run_command(cmd_list, cwd=self.working_dir)
        self.assertEqual(2, process_execute.process.returncode)


def get_expected_response(message):
    ip = get_ip_address()
    ip_str = ip.text.replace("\n", "")
    body = f'{{"message": "{message}", "location": "{ip_str}"}}'
    return {"body": body, "statusCode": 200}


def get_ip_address():
    ip_endpoint = "http://checkip.amazonaws.com/"
    try:
        ip = requests.get(ip_endpoint)
    except requests.RequestException as e:
        LOG.error("Failed to get ip {}".format(e))
        raise e
    return ip
