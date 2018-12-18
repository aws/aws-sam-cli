import threading
import shutil
import random
from mock import Mock
import time
from unittest import TestCase
import os

import requests

from samcli.local.lambda_service.local_lambda_invoke_service import LocalLambdaInvokeService
from tests.functional.function_code import nodejs_lambda, HELLO_FROM_LAMBDA, ECHO_CODE, THROW_ERROR_LAMBDA
from samcli.commands.local.lib import provider
from samcli.local.lambdafn.runtime import LambdaRuntime
from samcli.commands.local.lib.local_lambda import LocalLambdaRunner
from samcli.local.docker.manager import ContainerManager
from samcli.local.lambdafn.exceptions import FunctionNotFound
from samcli.local.layers.layer_downloader import LayerDownloader
from samcli.local.docker.lambda_image import LambdaImage


class TestLocalLambdaService(TestCase):

    @classmethod
    def mocked_function_provider(cls, function_name):
        if function_name == "HelloWorld":
            return cls.hello_world_function
        if function_name == "ThrowError":
            return cls.throw_error_function
        else:
            raise FunctionNotFound("Could not find Function")

    @classmethod
    def setUpClass(cls):
        cls.code_abs_path_for_throw_error = nodejs_lambda(THROW_ERROR_LAMBDA)

        # Let's convert this absolute path to relative path. Let the parent be the CWD, and codeuri be the folder
        cls.cwd_for_throw_error = os.path.dirname(cls.code_abs_path_for_throw_error)
        cls.code_uri_for_throw_error = os.path.relpath(cls.code_abs_path_for_throw_error, cls.cwd_for_throw_error)  # Get relative path with respect to CWD

        cls.code_abs_path = nodejs_lambda(HELLO_FROM_LAMBDA)

        # Let's convert this absolute path to relative path. Let the parent be the CWD, and codeuri be the folder
        cls.cwd = os.path.dirname(cls.code_abs_path)
        cls.code_uri = os.path.relpath(cls.code_abs_path, cls.cwd)  # Get relative path with respect to CWD

        cls.hello_world_function_name = "HelloWorld"

        cls.hello_world_function = provider.Function(name=cls.hello_world_function_name, runtime="nodejs4.3",
                                                     memory=256, timeout=5, handler="index.handler",
                                                     codeuri=cls.code_uri, environment=None, rolearn=None, layers=[])

        cls.throw_error_function_name = "ThrowError"

        cls.throw_error_function = provider.Function(name=cls.throw_error_function_name, runtime="nodejs4.3",
                                                     memory=256, timeout=5, handler="index.handler",
                                                     codeuri=cls.code_uri_for_throw_error, environment=None,
                                                     rolearn=None, layers=[])

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
        shutil.rmtree(cls.code_abs_path_for_throw_error)

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

    def test_request_a_function_that_throws_an_error(self):
        expected_data = {'errorMessage': 'something is wrong', 'errorType': 'Error','stackTrace': ['exports.handler (/var/task/index.js:3:17)']}

        response = requests.post(self.url + '/2015-03-31/functions/ThrowError/invocations')

        actual_data = response.json()
        acutal_error_type_header = response.headers.get('x-amz-function-error')

        self.assertEquals(actual_data, expected_data)
        self.assertEquals(acutal_error_type_header, 'Unhandled')
        self.assertEquals(response.status_code, 200)


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
                                         rolearn=None, layers=[])

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

    def test_binary_octet_stream_format(self):
        expected = {"key1": "value1"}

        response = requests.post(self.url + '/2015-03-31/functions/HelloWorld/invocations', json={"key1": "value1"}, headers={"Content-Type":"binary/octet-stream"})

        actual = response.json()

        self.assertEquals(actual, expected)
        self.assertEquals(response.status_code, 200)

    def test_function_executed_when_no_data_provided(self):
        expected = {}

        response = requests.post(self.url + '/2015-03-31/functions/HelloWorld/invocations')

        actual = response.json()

        self.assertEquals(actual, expected)
        self.assertEquals(response.status_code, 200)


class TestLocalLambdaService_NotSupportedRequests(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.code_abs_path = nodejs_lambda(ECHO_CODE)

        # Let's convert this absolute path to relative path. Let the parent be the CWD, and codeuri be the folder
        cls.cwd = os.path.dirname(cls.code_abs_path)
        cls.code_uri = os.path.relpath(cls.code_abs_path, cls.cwd)  # Get relative path with respect to CWD

        cls.function_name = "HelloWorld"

        cls.function = provider.Function(name=cls.function_name, runtime="nodejs4.3", memory=256, timeout=5,
                                         handler="index.handler", codeuri=cls.code_uri, environment=None,
                                         rolearn=None, layers=[])

        cls.mock_function_provider = Mock()
        cls.mock_function_provider.get.return_value = cls.function

        cls.service, cls.port, cls.url, cls.scheme = make_service(cls.mock_function_provider, cls.cwd)
        cls.service.create()
        # import pdb; pdb.set_trace()
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

    def test_query_string_parameters_in_request(self):
        expected = {"Type": "User",
             "Message": "Query Parameters are not supported"}

        response = requests.post(self.url + '/2015-03-31/functions/HelloWorld/invocations', json={"key1": "value1"}, params={"key": "value"})

        actual = response.json()

        self.assertEquals(actual, expected)
        self.assertEquals(response.status_code, 400)
        self.assertEquals(response.headers.get('x-amzn-errortype'), 'InvalidRequestContent')
        self.assertEquals(response.headers.get('Content-Type'),'application/json')

    def test_payload_is_not_json_serializable(self):
        expected = {"Type": "User",
                    "Message": "Could not parse request body into json: No JSON object could be decoded"}

        response = requests.post(self.url + '/2015-03-31/functions/HelloWorld/invocations', data='notat:asdfasdf')

        actual = response.json()

        self.assertEquals(actual, expected)
        self.assertEquals(response.status_code, 400)
        self.assertEquals(response.headers.get('x-amzn-errortype'), 'InvalidRequestContent')
        self.assertEquals(response.headers.get('Content-Type'), 'application/json')

    def test_log_type_tail_in_request(self):
        expected = {"Type": "LocalService", "Message": "log-type: Tail is not supported. None is only supported."}

        response = requests.post(self.url + '/2015-03-31/functions/HelloWorld/invocations', headers={'X-Amz-Log-Type': 'Tail'})

        actual = response.json()

        self.assertEquals(actual, expected)
        self.assertEquals(response.status_code, 501)
        self.assertEquals(response.headers.get('Content-Type'), 'application/json')
        self.assertEquals(response.headers.get('x-amzn-errortype'), 'NotImplemented')

    def test_log_type_tail_in_request_with_lowercase_header(self):
        expected = {"Type": "LocalService", "Message": "log-type: Tail is not supported. None is only supported."}

        response = requests.post(self.url + '/2015-03-31/functions/HelloWorld/invocations', headers={'x-amz-log-type': 'Tail'})

        actual = response.json()

        self.assertEquals(actual, expected)
        self.assertEquals(response.status_code, 501)
        self.assertEquals(response.headers.get('Content-Type'), 'application/json')
        self.assertEquals(response.headers.get('x-amzn-errortype'), 'NotImplemented')

    def test_invocation_type_event_in_request(self):
        expected = {"Type": "LocalService", "Message": "invocation-type: Event is not supported. RequestResponse is only supported."}

        response = requests.post(self.url + '/2015-03-31/functions/HelloWorld/invocations',
                                 headers={'X-Amz-Invocation-Type': 'Event'})

        actual = response.json()

        self.assertEquals(actual, expected)
        self.assertEquals(response.status_code, 501)
        self.assertEquals(response.headers.get('Content-Type'), 'application/json')
        self.assertEquals(response.headers.get('x-amzn-errortype'), 'NotImplemented')

    def test_invocation_type_dry_run_in_request(self):
        expected = {"Type": "LocalService", "Message": "invocation-type: DryRun is not supported. RequestResponse is only supported."}

        response = requests.post(self.url + '/2015-03-31/functions/HelloWorld/invocations',
                                 headers={'X-Amz-Invocation-Type': 'DryRun'})

        actual = response.json()

        self.assertEquals(actual, expected)
        self.assertEquals(response.status_code, 501)
        self.assertEquals(response.headers.get('Content-Type'), 'application/json')
        self.assertEquals(response.headers.get('x-amzn-errortype'), 'NotImplemented')

    def test_generic_404_error_when_request_to_nonexisting_endpoint(self):
        expected_data = {'Type': 'LocalService', 'Message': 'PathNotFoundException'}

        response = requests.post(self.url + '/some/random/path/that/does/not/exist')

        actual_data = response.json()

        self.assertEquals(actual_data, expected_data)
        self.assertEquals(response.status_code, 404)
        self.assertEquals(response.headers.get('x-amzn-errortype'), 'PathNotFoundLocally')


    def test_generic_405_error_when_request_path_with_invalid_method(self):
        expected_data = {'Type': 'LocalService', 'Message': 'MethodNotAllowedException'}

        response = requests.get(self.url + '/2015-03-31/functions/HelloWorld/invocations')

        actual_data = response.json()

        self.assertEquals(actual_data, expected_data)
        self.assertEquals(response.status_code, 405)
        self.assertEquals(response.headers.get('x-amzn-errortype'), 'MethodNotAllowedLocally')


def make_service(function_provider, cwd):
    port = random_port()
    manager = ContainerManager()
    layer_downloader = LayerDownloader("./", "./")
    image_builder = LambdaImage(layer_downloader, False, False)
    local_runtime = LambdaRuntime(manager, image_builder)
    lambda_runner = LocalLambdaRunner(local_runtime=local_runtime,
                                      function_provider=function_provider,
                                      cwd=cwd)

    service = LocalLambdaInvokeService(lambda_runner, port=port, host='127.0.0.1')

    scheme = "http"
    url = '{}://127.0.0.1:{}'.format(scheme, port)
    return service, port, url, scheme

def random_port():
    return random.randint(30000, 40000)