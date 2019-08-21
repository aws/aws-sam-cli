"""
Function test for Local API service
"""

import os
import shutil
import random
import threading
import requests
import time
import logging

from samcli.commands.local.lib import provider
from samcli.commands.local.lib.local_lambda import LocalLambdaRunner
from samcli.local.lambdafn.runtime import LambdaRuntime
from samcli.local.docker.manager import ContainerManager
from samcli.commands.local.lib.local_api_service import LocalApiService
from samcli.local.layers.layer_downloader import LayerDownloader
from samcli.local.docker.lambda_image import LambdaImage

from tests.functional.function_code import nodejs_lambda, API_GATEWAY_ECHO_EVENT
from unittest import TestCase
from mock import Mock, patch

logging.basicConfig(level=logging.INFO)


class TestFunctionalLocalLambda(TestCase):

    def setUp(self):
        self.host = "127.0.0.1"
        self.port = random.randint(30000, 40000)  # get a random port
        self.url = "http://{}:{}".format(self.host, self.port)

        self.code_abs_path = nodejs_lambda(API_GATEWAY_ECHO_EVENT)

        # Let's convert this absolute path to relative path. Let the parent be the CWD, and codeuri be the folder
        self.cwd = os.path.dirname(self.code_abs_path)
        self.code_uri = os.path.relpath(self.code_abs_path, self.cwd)  # Get relative path with respect to CWD

        # Setup a static file in the directory
        self.static_dir = "mystaticdir"
        self.static_file_name = "myfile.txt"
        self.static_file_content = "This is a static file"
        self._setup_static_file(os.path.join(self.cwd, self.static_dir),   # Create static directory with in cwd
                                self.static_file_name,
                                self.static_file_content)

        # Create one Lambda function
        self.function_name = "name"
        self.function = provider.Function(name=self.function_name, runtime="nodejs4.3", memory=256, timeout=5,
                                          handler="index.handler", codeuri=self.code_uri,
                                          environment={},
                                          rolearn=None, layers=[])
        self.mock_function_provider = Mock()
        self.mock_function_provider.get.return_value = self.function

        # Setup two APIs pointing to the same function
        apis = [
            provider.Api(path="/get", method="GET", function_name=self.function_name, cors="cors"),
            provider.Api(path="/post", method="POST", function_name=self.function_name, cors="cors"),
        ]
        self.api_provider_mock = Mock()
        self.api_provider_mock.get_all.return_value = apis

        # Now wire up the Lambda invoker and pass it through the context
        self.lambda_invoke_context_mock = Mock()
        manager = ContainerManager()
        layer_downloader = LayerDownloader("./", "./")
        lambda_image = LambdaImage(layer_downloader, False, False)
        local_runtime = LambdaRuntime(manager, lambda_image)
        lambda_runner = LocalLambdaRunner(local_runtime, self.mock_function_provider, self.cwd, env_vars_values=None,
                                          debug_context=None)
        self.lambda_invoke_context_mock.local_lambda_runner = lambda_runner
        self.lambda_invoke_context_mock.get_cwd.return_value = self.cwd

    def tearDown(self):
        shutil.rmtree(self.code_abs_path)

    @patch("samcli.commands.local.lib.local_api_service.SamApiProvider")
    def test_must_start_service_and_serve_endpoints(self, sam_api_provider_mock):
        sam_api_provider_mock.return_value = self.api_provider_mock

        local_service = LocalApiService(self.lambda_invoke_context_mock,
                                        self.port,
                                        self.host,
                                        None)  # No static directory

        self._start_service_thread(local_service)

        response = requests.get(self.url + '/get')
        self.assertEquals(response.status_code, 200)

        response = requests.post(self.url + '/post', {})
        self.assertEquals(response.status_code, 200)

        response = requests.get(self.url + '/post')
        self.assertEquals(response.status_code, 403)  # "HTTP GET /post" must not exist

    @patch("samcli.commands.local.lib.local_api_service.SamApiProvider")
    def test_must_serve_static_files(self, sam_api_provider_mock):
        sam_api_provider_mock.return_value = self.api_provider_mock

        local_service = LocalApiService(self.lambda_invoke_context_mock,
                                        self.port,
                                        self.host,
                                        self.static_dir)  # Mount the static directory

        self._start_service_thread(local_service)

        # NOTE: The URL does not contain the static_dir because this directory is mounted directly at /
        response = requests.get("{}/{}".format(self.url, self.static_file_name))

        self.assertEquals(response.status_code, 200)
        self.assertEquals(self.static_file_content, response.text)

    @staticmethod
    def _start_service_thread(service):
        t = threading.Thread(name='thread', target=service.start, args=())
        t.setDaemon(True)
        t.start()
        time.sleep(1)  # Wait for the Web server to spin up

    @staticmethod
    def _setup_static_file(directory, filename, contents):

        if not os.path.isdir(directory):
            os.mkdir(directory)

        with open(os.path.join(directory, filename), "w") as fp:
            fp.write(contents)

