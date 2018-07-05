import threading
import shutil
import random
from mock import Mock
import time
from unittest import TestCase
import os

import requests

from samcli.local.lambda_service.local_lambda_invoke_service import LocalLambdaInvokeService
from tests.functional.function_code import nodejs_lambda, HELLO_FROM_LAMBDA, ECHO_CODE
from samcli.commands.local.lib import provider
from samcli.local.lambdafn.runtime import LambdaRuntime
from samcli.commands.local.lib.local_lambda import LocalLambdaRunner
from samcli.local.docker.manager import ContainerManager
from samcli.local.lambdafn.exceptions import FunctionNotFound


class TestLocalLambdaService(TestCase):

    @classmethod
    def mocked_function_provider(cls, function_name):
        if function_name == "HelloWorld":
            return cls.function
        else:
            raise FunctionNotFound("Could not find Function")

    @classmethod
    def setUpClass(cls):
        cls.code_abs_path = nodejs_lambda(HELLO_FROM_LAMBDA)

        # Let's convert this absolute path to relative path. Let the parent be the CWD, and codeuri be the folder
        cls.cwd = os.path.dirname(cls.code_abs_path)
        cls.code_uri = os.path.relpath(cls.code_abs_path, cls.cwd)  # Get relative path with respect to CWD

        cls.function_name = "HelloWorld"

        cls.function = provider.Function(name=cls.function_name, runtime="nodejs4.3", memory=256, timeout=5,
                                         handler="index.handler", codeuri=cls.code_uri, environment=None,
                                         rolearn=None)

        cls.mock_function_provider = Mock()
        cls.mock_function_provider.get.side_effect = cls.mocked_function_provider

        cls.service, cls.port, cls.url, cls.scheme = make_service(cls.mock_function_provider, cls.cwd)
        cls.service.create()
        t = threading.Thread(name='thread', target=cls.service.run, args=())
        t.setDaemon(True)
        t.start()
        time.sleep(1)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.code_abs_path)

    def setUp(self):
        # Print full diff when comparing large dictionaries
        self.maxDiff = None

    def test_lambda_str_response_is_returned(self):
        expected = 'Hello from Lambda'

        response = requests.post(self.url + '/2015-03-31/functions/HelloWorld/invocations')

        actual = response.json()

        self.assertEquals(actual, expected)
        self.assertEquals(response.status_code, 200)

    def test_request_with_non_existing_function(self):
        expected_data = {"Message": "Function not found: arn:aws:lambda:us-west-2:012345678901:function:{}".format('IDoNotExist'),
             "Type": "User"}

        response = requests.post(self.url + '/2015-03-31/functions/IDoNotExist/invocations')

        actual_data = response.json()
        acutal_error_type_header = response.headers.get('x-amzn-errortype')

        self.assertEquals(actual_data, expected_data)
        self.assertEquals(acutal_error_type_header, 'ResourceNotFound')
        self.assertEquals(response.status_code, 404)

class TestLocalEchoLambdaService(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.code_abs_path = nodejs_lambda(ECHO_CODE)

        # Let's convert this absolute path to relative path. Let the parent be the CWD, and codeuri be the folder
        cls.cwd = os.path.dirname(cls.code_abs_path)
        cls.code_uri = os.path.relpath(cls.code_abs_path, cls.cwd)  # Get relative path with respect to CWD

        cls.function_name = "HelloWorld"

        cls.function = provider.Function(name=cls.function_name, runtime="nodejs4.3", memory=256, timeout=5,
                                         handler="index.handler", codeuri=cls.code_uri, environment=None,
                                         rolearn=None)

        cls.mock_function_provider = Mock()
        cls.mock_function_provider.get.return_value = cls.function

        cls.service, cls.port, cls.url, cls.scheme = make_service(cls.mock_function_provider, cls.cwd)
        cls.service.create()
        t = threading.Thread(name='thread', target=cls.service.run, args=())
        t.setDaemon(True)
        t.start()
        time.sleep(1)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.code_abs_path)

    def setUp(self):
        # Print full diff when comparing large dictionaries
        self.maxDiff = None

    def test_mock_response_is_returned(self):
        expected = {"key1": "value1"}

        response = requests.post(self.url + '/2015-03-31/functions/HelloWorld/invocations', json={"key1": "value1"})

        actual = response.json()

        self.assertEquals(actual, expected)
        self.assertEquals(response.status_code, 200)


def make_service(function_provider, cwd):
    port = random_port()
    manager = ContainerManager()
    local_runtime = LambdaRuntime(manager)
    lambda_runner = LocalLambdaRunner(local_runtime=local_runtime,
                                      function_provider=function_provider,
                                      cwd=cwd)

    service = LocalLambdaInvokeService(lambda_runner, port=port, host='127.0.0.1')

    scheme = "http"
    url = '{}://127.0.0.1:{}'.format(scheme, port)
    return service, port, url, scheme

def random_port():
    return random.randint(30000, 40000)