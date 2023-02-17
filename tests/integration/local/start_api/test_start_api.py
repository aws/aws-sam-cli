import base64
import shutil
import uuid
import random
from pathlib import Path
from typing import Dict

import requests
from http.client import HTTPConnection
from concurrent.futures import ThreadPoolExecutor, as_completed
from time import time, sleep

import pytest
from parameterized import parameterized_class

from samcli.commands.local.cli_common.invoke_context import ContainersInitializationMode
from samcli.local.apigw.local_apigw_service import Route
from .start_api_integ_base import StartApiIntegBaseClass, WatchWarmContainersIntegBaseClass
from ..invoke.layer_utils import LayerUtils


@parameterized_class(
    ("template_path",),
    [
        ("/testdata/start_api/template.yaml",),
        ("/testdata/start_api/nested-templates/template-parent.yaml",),
        ("/testdata/start_api/cdk/template_cdk.yaml",),
    ],
)
class TestServiceHTTP10(StartApiIntegBaseClass):
    """
    Testing general requirements around the Service that powers `sam local start-api`
    """

    def setUp(self):
        self.url = "http://127.0.0.1:{}".format(self.port)
        HTTPConnection._http_vsn_str = "HTTP/1.0"

    def test_static_directory(self):
        pass

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_calling_proxy_endpoint_http10(self):
        response = requests.get(self.url + "/proxypath/this/is/some/path", timeout=300)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"hello": "world"})
        self.assertEqual(response.raw.version, 11)  # Checks if the response is HTTP/1.1 version

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_get_call_with_path_setup_with_any_implicit_api_http10(self):
        """
        Get Request to a path that was defined as ANY in SAM through AWS::Serverless::Function Events
        """
        response = requests.get(self.url + "/anyandall", timeout=300)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"hello": "world"})
        self.assertEqual(response.raw.version, 11)

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_post_call_with_path_setup_with_any_implicit_api_http10(self):
        """
        Post Request to a path that was defined as ANY in SAM through AWS::Serverless::Function Events
        """
        response = requests.post(self.url + "/anyandall", json={}, timeout=300)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"hello": "world"})
        self.assertEqual(response.raw.version, 11)

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_put_call_with_path_setup_with_any_implicit_api_http10(self):
        """
        Put Request to a path that was defined as ANY in SAM through AWS::Serverless::Function Events
        """
        response = requests.put(self.url + "/anyandall", json={}, timeout=300)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"hello": "world"})
        self.assertEqual(response.raw.version, 11)

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_head_call_with_path_setup_with_any_implicit_api_http10(self):
        """
        Head Request to a path that was defined as ANY in SAM through AWS::Serverless::Function Events
        """
        response = requests.head(self.url + "/anyandall", timeout=300)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.raw.version, 11)

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_delete_call_with_path_setup_with_any_implicit_api_http10(self):
        """
        Delete Request to a path that was defined as ANY in SAM through AWS::Serverless::Function Events
        """
        response = requests.delete(self.url + "/anyandall", timeout=300)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"hello": "world"})
        self.assertEqual(response.raw.version, 11)

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_options_call_with_path_setup_with_any_implicit_api_http10(self):
        """
        Options Request to a path that was defined as ANY in SAM through AWS::Serverless::Function Events
        """
        response = requests.options(self.url + "/anyandall", timeout=300)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.raw.version, 11)

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_patch_call_with_path_setup_with_any_implicit_api_http10(self):
        """
        Patch Request to a path that was defined as ANY in SAM through AWS::Serverless::Function Events
        """
        response = requests.patch(self.url + "/anyandall", timeout=300)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"hello": "world"})
        self.assertEqual(response.raw.version, 11)

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_large_input_request_http10(self):
        # not exact 6 mega, as local start-api sends extra data with the input data
        around_six_mega = 6 * 1024 * 1024 - 2 * 1024
        data = "a" * around_six_mega
        response = requests.post(self.url + "/echoeventbody", data=data, timeout=300)

        self.assertEqual(response.status_code, 200)
        response_data = response.json()
        self.assertEqual(response_data.get("body"), data)
        self.assertEqual(response.raw.version, 11)


@parameterized_class(
    ("template_path",),
    [
        ("/testdata/start_api/template.yaml",),
        ("/testdata/start_api/cdk/template_cdk.yaml",),
    ],
)
class TestParallelRequests(StartApiIntegBaseClass):
    """
    Test Class centered around sending parallel requests to the service `sam local start-api`
    """

    def setUp(self):
        self.url = "http://127.0.0.1:{}".format(self.port)
        HTTPConnection._http_vsn_str = "HTTP/1.1"

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_same_endpoint(self):
        """
        Send two requests to the same path at the same time. This is to ensure we can handle
        multiple requests at once and do not block/queue up requests
        """
        number_of_requests = 10
        start_time = time()
        with ThreadPoolExecutor(number_of_requests) as thread_pool:
            futures = [
                thread_pool.submit(requests.get, self.url + "/sleepfortenseconds/function1", timeout=300)
                for _ in range(0, number_of_requests)
            ]
            results = [r.result() for r in as_completed(futures)]

            end_time = time()

            self.assertEqual(len(results), 10)
            self.assertGreater(end_time - start_time, 10)

            for result in results:
                self.assertEqual(result.status_code, 200)
                self.assertEqual(result.json(), {"message": "HelloWorld! I just slept and waking up."})
                self.assertEqual(result.raw.version, 11)  # Checks if the response is HTTP/1.1 version

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_different_endpoints(self):
        """
        Send two requests to different paths at the same time. This is to ensure we can handle
        multiple requests for different paths and do not block/queue up the requests
        """
        number_of_requests = 10
        start_time = time()
        with ThreadPoolExecutor(10) as thread_pool:
            test_url_paths = ["/sleepfortenseconds/function0", "/sleepfortenseconds/function1"]

            futures = [
                thread_pool.submit(
                    requests.get, self.url + test_url_paths[function_num % len(test_url_paths)], timeout=300
                )
                for function_num in range(0, number_of_requests)
            ]
            results = [r.result() for r in as_completed(futures)]

            end_time = time()

            self.assertEqual(len(results), 10)
            self.assertGreater(end_time - start_time, 10)

            for result in results:
                self.assertEqual(result.status_code, 200)
                self.assertEqual(result.json(), {"message": "HelloWorld! I just slept and waking up."})
                self.assertEqual(result.raw.version, 11)


@parameterized_class(
    ("template_path",),
    [
        ("/testdata/start_api/template.yaml",),
        ("/testdata/start_api/cdk/template_cdk.yaml",),
    ],
)
class TestServiceErrorResponses(StartApiIntegBaseClass):
    """
    Test Class centered around the Error Responses the Service can return for a given api
    """

    def setUp(self):
        self.url = "http://127.0.0.1:{}".format(self.port)

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_invalid_http_verb_for_endpoint(self):
        response = requests.get(self.url + "/id", timeout=300)

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json(), {"message": "Missing Authentication Token"})
        self.assertEqual(response.raw.version, 11)  # Checks if the response is HTTP/1.1 version

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_invalid_response_from_lambda(self):
        response = requests.get(self.url + "/invalidresponsereturned", timeout=300)

        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.json(), {"message": "Internal server error"})
        self.assertEqual(response.raw.version, 11)

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_invalid_json_response_from_lambda(self):
        response = requests.get(self.url + "/invalidresponsehash", timeout=300)

        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.json(), {"message": "Internal server error"})
        self.assertEqual(response.raw.version, 11)

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_request_timeout(self):
        pass


class TestServiceFunctionWithInlineCode(StartApiIntegBaseClass):
    template_path = "/testdata/start_api/template-inlinecode.yaml"

    def setUp(self):
        self.url = "http://127.0.0.1:{}".format(self.port)

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_function_without_inline_code_endpoint(self):
        response = requests.get(self.url + "/no_inlinecode", timeout=300)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"hello": "world"})

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_function_with_inline_code_endpoint(self):
        response = requests.get(self.url + "/inlinecode", timeout=300)

        self.assertEqual(response.status_code, 501)
        self.assertEqual(
            response.json(),
            {
                "message": "Inline code is not supported for sam local commands."
                " Please write your code in a separate file."
            },
        )


@parameterized_class(
    ("template_path",),
    [
        ("/testdata/start_api/template.yaml",),
        ("/testdata/start_api/nested-templates/template-parent.yaml",),
        ("/testdata/start_api/cdk/template_cdk.yaml",),
    ],
)
class TestService(StartApiIntegBaseClass):
    """
    Testing general requirements around the Service that powers `sam local start-api`
    """

    def setUp(self):
        self.url = "http://127.0.0.1:{}".format(self.port)

    def test_static_directory(self):
        pass

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_calling_proxy_endpoint(self):
        response = requests.get(self.url + "/proxypath/this/is/some/path", timeout=300)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"hello": "world"})
        self.assertEqual(response.raw.version, 11)  # Checks if the response is HTTP/1.1 version

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_get_call_with_path_setup_with_any_implicit_api(self):
        """
        Get Request to a path that was defined as ANY in SAM through AWS::Serverless::Function Events
        """
        response = requests.get(self.url + "/anyandall", timeout=300)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"hello": "world"})
        self.assertEqual(response.raw.version, 11)

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_post_call_with_path_setup_with_any_implicit_api(self):
        """
        Post Request to a path that was defined as ANY in SAM through AWS::Serverless::Function Events
        """
        response = requests.post(self.url + "/anyandall", json={}, timeout=300)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"hello": "world"})
        self.assertEqual(response.raw.version, 11)

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_put_call_with_path_setup_with_any_implicit_api(self):
        """
        Put Request to a path that was defined as ANY in SAM through AWS::Serverless::Function Events
        """
        response = requests.put(self.url + "/anyandall", json={}, timeout=300)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"hello": "world"})
        self.assertEqual(response.raw.version, 11)

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_head_call_with_path_setup_with_any_implicit_api(self):
        """
        Head Request to a path that was defined as ANY in SAM through AWS::Serverless::Function Events
        """
        response = requests.head(self.url + "/anyandall", timeout=300)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.raw.version, 11)

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_delete_call_with_path_setup_with_any_implicit_api(self):
        """
        Delete Request to a path that was defined as ANY in SAM through AWS::Serverless::Function Events
        """
        response = requests.delete(self.url + "/anyandall", timeout=300)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"hello": "world"})
        self.assertEqual(response.raw.version, 11)

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_options_call_with_path_setup_with_any_implicit_api(self):
        """
        Options Request to a path that was defined as ANY in SAM through AWS::Serverless::Function Events
        """
        response = requests.options(self.url + "/anyandall", timeout=300)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.raw.version, 11)

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_patch_call_with_path_setup_with_any_implicit_api(self):
        """
        Patch Request to a path that was defined as ANY in SAM through AWS::Serverless::Function Events
        """
        response = requests.patch(self.url + "/anyandall", timeout=300)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"hello": "world"})
        self.assertEqual(response.raw.version, 11)

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_large_input_request(self):
        # not exact 6 mega, as local start-api sends extra data with the input data
        around_six_mega = 6 * 1024 * 1024 - 2 * 1024
        data = "a" * around_six_mega
        response = requests.post(self.url + "/echoeventbody", data=data, timeout=300)

        self.assertEqual(response.status_code, 200)
        response_data = response.json()
        self.assertEqual(response_data.get("body"), data)
        self.assertEqual(response.raw.version, 11)


@parameterized_class(
    ("template_path",),
    [
        ("/testdata/start_api/template-http-api.yaml",),
        ("/testdata/start_api/nested-templates/template-http-api-parent.yaml",),
    ],
)
class TestServiceWithHttpApi(StartApiIntegBaseClass):
    """
    Testing general requirements around the Service that powers `sam local start-api`
    """

    def setUp(self):
        self.url = "http://127.0.0.1:{}".format(self.port)

    def test_static_directory(self):
        pass

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_calling_proxy_endpoint(self):
        response = requests.get(self.url + "/proxypath/this/is/some/path", timeout=300)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"hello": "world"})
        self.assertEqual(response.raw.version, 11)

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_get_call_with_path_setup_with_any_implicit_api(self):
        """
        Get Request to a path that was defined as ANY in SAM through AWS::Serverless::Function Events
        """
        response = requests.get(self.url + "/anyandall", timeout=300)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"hello": "world"})
        self.assertEqual(response.raw.version, 11)

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_post_call_with_path_setup_with_any_implicit_api(self):
        """
        Post Request to a path that was defined as ANY in SAM through AWS::Serverless::Function Events
        """
        response = requests.post(self.url + "/anyandall", json={}, timeout=300)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"hello": "world"})
        self.assertEqual(response.raw.version, 11)

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_put_call_with_path_setup_with_any_implicit_api(self):
        """
        Put Request to a path that was defined as ANY in SAM through AWS::Serverless::Function Events
        """
        response = requests.put(self.url + "/anyandall", json={}, timeout=300)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"hello": "world"})
        self.assertEqual(response.raw.version, 11)

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_head_call_with_path_setup_with_any_implicit_api(self):
        """
        Head Request to a path that was defined as ANY in SAM through AWS::Serverless::Function Events
        """
        response = requests.head(self.url + "/anyandall", timeout=300)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.raw.version, 11)

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_delete_call_with_path_setup_with_any_implicit_api(self):
        """
        Delete Request to a path that was defined as ANY in SAM through AWS::Serverless::Function Events
        """
        response = requests.delete(self.url + "/anyandall", timeout=300)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"hello": "world"})
        self.assertEqual(response.raw.version, 11)

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_options_call_with_path_setup_with_any_implicit_api(self):
        """
        Options Request to a path that was defined as ANY in SAM through AWS::Serverless::Function Events
        """
        response = requests.options(self.url + "/anyandall", timeout=300)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.raw.version, 11)

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_patch_call_with_path_setup_with_any_implicit_api(self):
        """
        Patch Request to a path that was defined as ANY in SAM through AWS::Serverless::Function Events
        """
        response = requests.patch(self.url + "/anyandall", timeout=300)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"hello": "world"})
        self.assertEqual(response.raw.version, 11)

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_valid_v2_lambda_json_response(self):
        """
        Patch Request to a path that was defined as ANY in SAM through AWS::Serverless::Function Events
        """
        response = requests.get(self.url + "/validv2responsehash", timeout=300)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"foo": "bar"})
        self.assertEqual(response.raw.version, 11)

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_invalid_v1_lambda_json_response(self):
        """
        Patch Request to a path that was defined as ANY in SAM through AWS::Serverless::Function Events
        """
        response = requests.get(self.url + "/invalidv1responsehash", timeout=300)

        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.json(), {"message": "Internal server error"})
        self.assertEqual(response.raw.version, 11)

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_valid_v2_lambda_string_response(self):
        """
        Patch Request to a path that was defined as ANY in SAM through AWS::Serverless::Function Events
        """
        response = requests.get(self.url + "/validv2responsestring", timeout=300)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.text, "This is invalid")
        self.assertEqual(response.raw.version, 11)

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_valid_v2_lambda_integer_response(self):
        """
        Patch Request to a path that was defined as ANY in SAM through AWS::Serverless::Function Events
        """
        response = requests.get(self.url + "/validv2responseinteger", timeout=300)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.text, "2")
        self.assertEqual(response.raw.version, 11)

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_v2_lambda_response_skip_unexpected_fields(self):
        """
        Patch Request to a path that was defined as ANY in SAM through AWS::Serverless::Function Events
        """
        response = requests.get(self.url + "/invalidv2response", timeout=300)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"hello": "world"})
        self.assertEqual(response.raw.version, 11)

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_invalid_v1_lambda_string_response(self):
        """
        Patch Request to a path that was defined as ANY in SAM through AWS::Serverless::Function Events
        """
        response = requests.get(self.url + "/invalidv1responsestring", timeout=300)

        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.json(), {"message": "Internal server error"})
        self.assertEqual(response.raw.version, 11)


class TestStartApiWithSwaggerApis(StartApiIntegBaseClass):
    template_path = "/testdata/start_api/swagger-template.yaml"
    binary_data_file = "testdata/start_api/binarydata.gif"

    def setUp(self):
        self.url = "http://127.0.0.1:{}".format(self.port)

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_get_call_with_path_setup_with_any_swagger(self):
        """
        Get Request to a path that was defined as ANY in SAM through Swagger
        """
        response = requests.get(self.url + "/anyandall", timeout=300)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"hello": "world"})

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_parse_swagger_body_with_non_case_sensitive_integration_type(self):
        """
        Get Request to a path that was defined as ANY in SAM through Swagger
        """
        response = requests.get(self.url + "/nonsensitiveanyandall", timeout=300)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"hello": "world"})

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_post_call_with_path_setup_with_any_swagger(self):
        """
        Post Request to a path that was defined as ANY in SAM through Swagger
        """
        response = requests.post(self.url + "/anyandall", json={}, timeout=300)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"hello": "world"})

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_put_call_with_path_setup_with_any_swagger(self):
        """
        Put Request to a path that was defined as ANY in SAM through Swagger
        """
        response = requests.put(self.url + "/anyandall", json={}, timeout=300)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"hello": "world"})

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_head_call_with_path_setup_with_any_swagger(self):
        """
        Head Request to a path that was defined as ANY in SAM through Swagger
        """
        response = requests.head(self.url + "/anyandall", timeout=300)

        self.assertEqual(response.status_code, 200)

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_delete_call_with_path_setup_with_any_swagger(self):
        """
        Delete Request to a path that was defined as ANY in SAM through Swagger
        """
        response = requests.delete(self.url + "/anyandall", timeout=300)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"hello": "world"})

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_options_call_with_path_setup_with_any_swagger(self):
        """
        Options Request to a path that was defined as ANY in SAM through Swagger
        """
        response = requests.options(self.url + "/anyandall", timeout=300)

        self.assertEqual(response.status_code, 200)

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_patch_call_with_path_setup_with_any_swagger(self):
        """
        Patch Request to a path that was defined as ANY in SAM through Swagger
        """
        response = requests.patch(self.url + "/anyandall", timeout=300)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"hello": "world"})

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_function_not_defined_in_template(self):
        response = requests.get(self.url + "/nofunctionfound", timeout=300)

        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.json(), {"message": "No function defined for resource method"})

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_function_with_no_api_event_is_reachable(self):
        response = requests.get(self.url + "/functionwithnoapievent", timeout=300)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"hello": "world"})

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_lambda_function_resource_is_reachable(self):
        response = requests.get(self.url + "/nonserverlessfunction", timeout=300)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"hello": "world"})

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_binary_request(self):
        """
        This tests that the service can accept and invoke a lambda when given binary data in a request
        """
        input_data = self.get_binary_data(self.binary_data_file)
        response = requests.post(
            self.url + "/echobase64eventbody", headers={"Content-Type": "image/gif"}, data=input_data, timeout=300
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get("Content-Type"), "image/gif")
        self.assertEqual(response.content, input_data)

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_binary_response(self):
        """
        Binary data is returned correctly
        """
        expected = self.get_binary_data(self.binary_data_file)

        response = requests.get(self.url + "/base64response", timeout=300)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get("Content-Type"), "image/gif")
        self.assertEqual(response.content, expected)

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_non_decoded_binary_response(self):
        """
        Binary data is returned correctly
        """
        expected = base64.b64encode(self.get_binary_data(self.binary_data_file))

        response = requests.get(self.url + "/nondecodedbase64response", timeout=300)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get("Content-Type"), "image/gif")
        self.assertEqual(response.content, expected)

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_decoded_binary_response_base64encoded_field(self):
        """
        Binary data is returned correctly
        """
        expected = self.get_binary_data(self.binary_data_file)

        response = requests.get(self.url + "/decodedbase64responsebas64encoded", timeout=300)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get("Content-Type"), "image/gif")
        self.assertEqual(response.content, expected)

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_decoded_binary_response_base64encoded_field_is_priority(self):
        """
        Binary data is returned correctly
        """
        expected = base64.b64encode(self.get_binary_data(self.binary_data_file))

        response = requests.get(self.url + "/decodedbase64responsebas64encodedpriority", timeout=300)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get("Content-Type"), "image/gif")
        self.assertEqual(response.content, expected)


class TestStartApiWithSwaggerHttpApis(StartApiIntegBaseClass):
    template_path = "/testdata/start_api/swagger-template-http-api.yaml"
    binary_data_file = "testdata/start_api/binarydata.gif"

    def setUp(self):
        self.url = "http://127.0.0.1:{}".format(self.port)

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_get_call_with_path_setup_with_any_swagger(self):
        """
        Get Request to a path that was defined as ANY in SAM through Swagger
        """
        response = requests.get(self.url + "/httpapi-anyandall", timeout=300)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"hello": "world"})

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_post_call_with_path_setup_with_any_swagger(self):
        """
        Post Request to a path that was defined as ANY in SAM through Swagger
        """
        response = requests.post(self.url + "/httpapi-anyandall", json={}, timeout=300)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"hello": "world"})

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_put_call_with_path_setup_with_any_swagger(self):
        """
        Put Request to a path that was defined as ANY in SAM through Swagger
        """
        response = requests.put(self.url + "/httpapi-anyandall", json={}, timeout=300)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"hello": "world"})

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_head_call_with_path_setup_with_any_swagger(self):
        """
        Head Request to a path that was defined as ANY in SAM through Swagger
        """
        response = requests.head(self.url + "/httpapi-anyandall", timeout=300)

        self.assertEqual(response.status_code, 200)

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_delete_call_with_path_setup_with_any_swagger(self):
        """
        Delete Request to a path that was defined as ANY in SAM through Swagger
        """
        response = requests.delete(self.url + "/httpapi-anyandall", timeout=300)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"hello": "world"})

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_options_call_with_path_setup_with_any_swagger(self):
        """
        Options Request to a path that was defined as ANY in SAM through Swagger
        """
        response = requests.options(self.url + "/httpapi-anyandall", timeout=300)

        self.assertEqual(response.status_code, 200)

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_patch_call_with_path_setup_with_any_swagger(self):
        """
        Patch Request to a path that was defined as ANY in SAM through Swagger
        """
        response = requests.patch(self.url + "/httpapi-anyandall", timeout=300)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"hello": "world"})

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_http_api_payload_v1_should_not_have_operation_id(self):
        response = requests.get(self.url + "/httpapi-operation-id-v1", timeout=300)
        self.assertEqual(response.status_code, 200)

        response_data = response.json()
        self.assertEqual(response_data.get("version", {}), "1.0")
        # operationName or operationId shouldn't be processed by Httpapi swaggers
        request_context_keys = [key.lower() for key in response_data.get("requestContext", {}).keys()]
        self.assertTrue("operationid" not in request_context_keys)
        self.assertTrue("operationname" not in request_context_keys)

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_http_api_payload_v2_should_not_have_operation_id(self):
        response = requests.get(self.url + "/httpapi-operation-id-v2", timeout=300)
        self.assertEqual(response.status_code, 200)

        response_data = response.json()
        self.assertEqual(response_data.get("version", {}), "2.0")
        # operationName or operationId shouldn't be processed by Httpapi swaggers
        request_context_keys = [key.lower() for key in response_data.get("requestContext", {}).keys()]
        self.assertTrue("operationid" not in request_context_keys)
        self.assertTrue("operationname" not in request_context_keys)


class TestStartApiWithSwaggerRestApis(StartApiIntegBaseClass):
    template_path = "/testdata/start_api/swagger-rest-api-template.yaml"
    binary_data_file = "testdata/start_api/binarydata.gif"

    def setUp(self):
        self.url = "http://127.0.0.1:{}".format(self.port)

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_get_call_with_path_setup_with_any_swagger(self):
        """
        Get Request to a path that was defined as ANY in SAM through Swagger
        """
        response = requests.get(self.url + "/anyandall", timeout=300)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"hello": "world"})

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_post_call_with_path_setup_with_any_swagger(self):
        """
        Post Request to a path that was defined as ANY in SAM through Swagger
        """
        response = requests.post(self.url + "/anyandall", json={}, timeout=300)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"hello": "world"})

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_put_call_with_path_setup_with_any_swagger(self):
        """
        Put Request to a path that was defined as ANY in SAM through Swagger
        """
        response = requests.put(self.url + "/anyandall", json={}, timeout=300)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"hello": "world"})

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_head_call_with_path_setup_with_any_swagger(self):
        """
        Head Request to a path that was defined as ANY in SAM through Swagger
        """
        response = requests.head(self.url + "/anyandall", timeout=300)

        self.assertEqual(response.status_code, 200)

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_delete_call_with_path_setup_with_any_swagger(self):
        """
        Delete Request to a path that was defined as ANY in SAM through Swagger
        """
        response = requests.delete(self.url + "/anyandall", timeout=300)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"hello": "world"})

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_options_call_with_path_setup_with_any_swagger(self):
        """
        Options Request to a path that was defined as ANY in SAM through Swagger
        """
        response = requests.options(self.url + "/anyandall", timeout=300)

        self.assertEqual(response.status_code, 200)

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_patch_call_with_path_setup_with_any_swagger(self):
        """
        Patch Request to a path that was defined as ANY in SAM through Swagger
        """
        response = requests.patch(self.url + "/anyandall", timeout=300)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"hello": "world"})

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_function_not_defined_in_template(self):
        response = requests.get(self.url + "/nofunctionfound", timeout=300)

        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.json(), {"message": "No function defined for resource method"})

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_lambda_function_resource_is_reachable(self):
        response = requests.get(self.url + "/nonserverlessfunction", timeout=300)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"hello": "world"})

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_binary_request(self):
        """
        This tests that the service can accept and invoke a lambda when given binary data in a request
        """
        input_data = self.get_binary_data(self.binary_data_file)
        response = requests.post(
            self.url + "/echobase64eventbody", headers={"Content-Type": "image/gif"}, data=input_data, timeout=300
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get("Content-Type"), "image/gif")
        self.assertEqual(response.content, input_data)

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_binary_response(self):
        """
        Binary data is returned correctly
        """
        expected = self.get_binary_data(self.binary_data_file)

        response = requests.get(self.url + "/base64response", timeout=300)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get("Content-Type"), "image/gif")
        self.assertEqual(response.content, expected)

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_rest_api_operation_id(self):
        """
        Binary data is returned correctly
        """
        response = requests.get(self.url + "/printeventwithoperationidfunction", timeout=300)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json().get("requestContext", {}).get("operationName"), "MyOperationName")


class TestServiceResponses(StartApiIntegBaseClass):
    """
    Test Class centered around the different responses that can happen in Lambda and pass through start-api
    """

    template_path = "/testdata/start_api/template.yaml"
    binary_data_file = "testdata/start_api/binarydata.gif"

    def setUp(self):
        self.url = "http://127.0.0.1:{}".format(self.port)

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_multiple_headers_response(self):
        response = requests.get(self.url + "/multipleheaders", timeout=300)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get("Content-Type"), "text/plain")
        self.assertEqual(response.headers.get("MyCustomHeader"), "Value1, Value2")

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_multiple_headers_overrides_headers_response(self):
        response = requests.get(self.url + "/multipleheadersoverridesheaders", timeout=300)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get("Content-Type"), "text/plain")
        self.assertEqual(response.headers.get("MyCustomHeader"), "Value1, Value2, Custom")

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_binary_response(self):
        """
        Binary data is returned correctly
        """
        expected = self.get_binary_data(self.binary_data_file)

        response = requests.get(self.url + "/base64response", timeout=300)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get("Content-Type"), "image/gif")
        self.assertEqual(response.content, expected)

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_default_header_content_type(self):
        """
        Test that if no ContentType is given the default is "application/json"
        """
        response = requests.get(self.url + "/onlysetstatuscode", timeout=300)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode("utf-8"), "")
        self.assertEqual(response.headers.get("Content-Type"), "application/json")

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_default_status_code(self):
        """
        Test that if no status_code is given, the status code is 200
        :return:
        """
        response = requests.get(self.url + "/onlysetbody", timeout=300)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"hello": "world"})

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_slash_after_url_path(self):
        """
        Test that if no status_code is given, the status code is 200
        :return:
        """
        response = requests.get(self.url + "/onlysetbody/", timeout=300)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"hello": "world"})

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_string_status_code(self):
        """
        Test that an integer-string can be returned as the status code
        """
        response = requests.get(self.url + "/stringstatuscode", timeout=300)

        self.assertEqual(response.status_code, 200)

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_default_body(self):
        """
        Test that if no body is given, the response is ''
        """
        response = requests.get(self.url + "/onlysetstatuscode", timeout=300)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode("utf-8"), "")

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_function_writing_to_stdout(self):
        response = requests.get(self.url + "/writetostdout", timeout=300)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"hello": "world"})

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_function_writing_to_stderr(self):
        response = requests.get(self.url + "/writetostderr", timeout=300)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"hello": "world"})

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_integer_body(self):
        response = requests.get(self.url + "/echo_integer_body", timeout=300)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode("utf-8"), "42")


class TestServiceRequests(StartApiIntegBaseClass):
    """
    Test Class centered around the different requests that can happen
    """

    template_path = "/testdata/start_api/template.yaml"
    binary_data_file = "testdata/start_api/binarydata.gif"

    def setUp(self):
        self.url = "http://127.0.0.1:{}".format(self.port)

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_binary_request(self):
        """
        This tests that the service can accept and invoke a lambda when given binary data in a request
        """
        input_data = self.get_binary_data(self.binary_data_file)
        response = requests.post(
            self.url + "/echobase64eventbody", headers={"Content-Type": "image/gif"}, data=input_data, timeout=300
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get("Content-Type"), "image/gif")
        self.assertEqual(response.content, input_data)

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_request_with_form_data(self):
        """
        Form-encoded data should be put into the Event to Lambda
        """
        response = requests.post(
            self.url + "/echoeventbody",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data="key=value",
            timeout=300,
        )

        self.assertEqual(response.status_code, 200)

        response_data = response.json()

        self.assertEqual(response_data.get("headers").get("Content-Type"), "application/x-www-form-urlencoded")
        self.assertEqual(response_data.get("body"), "key=value")

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_request_to_an_endpoint_with_two_different_handlers(self):
        response = requests.get(self.url + "/echoeventbody", timeout=300)

        self.assertEqual(response.status_code, 200)

        response_data = response.json()

        self.assertEqual(response_data.get("handler"), "echo_event_handler_2")

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_request_with_multi_value_headers(self):
        response = requests.get(
            self.url + "/echoeventbody",
            headers={"Content-Type": "application/x-www-form-urlencoded, image/gif"},
            timeout=300,
        )

        self.assertEqual(response.status_code, 200)
        response_data = response.json()
        self.assertEqual(
            response_data.get("multiValueHeaders").get("Content-Type"), ["application/x-www-form-urlencoded, image/gif"]
        )
        self.assertEqual(
            response_data.get("headers").get("Content-Type"), "application/x-www-form-urlencoded, image/gif"
        )

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_request_with_query_params(self):
        """
        Query params given should be put into the Event to Lambda
        """
        response = requests.get(self.url + "/id/4", params={"key": "value"}, timeout=300)

        self.assertEqual(response.status_code, 200)

        response_data = response.json()

        self.assertEqual(response_data.get("queryStringParameters"), {"key": "value"})
        self.assertEqual(response_data.get("multiValueQueryStringParameters"), {"key": ["value"]})

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_request_with_list_of_query_params(self):
        """
        Query params given should be put into the Event to Lambda
        """
        response = requests.get(self.url + "/id/4", params={"key": ["value", "value2"]}, timeout=300)

        self.assertEqual(response.status_code, 200)

        response_data = response.json()

        self.assertEqual(response_data.get("queryStringParameters"), {"key": "value2"})
        self.assertEqual(response_data.get("multiValueQueryStringParameters"), {"key": ["value", "value2"]})

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_request_with_path_params(self):
        """
        Path Parameters given should be put into the Event to Lambda
        """
        response = requests.get(self.url + "/id/4", timeout=300)

        self.assertEqual(response.status_code, 200)

        response_data = response.json()

        self.assertEqual(response_data.get("pathParameters"), {"id": "4"})

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_request_with_many_path_params(self):
        """
        Path Parameters given should be put into the Event to Lambda
        """
        response = requests.get(self.url + "/id/4/user/jacob", timeout=300)

        self.assertEqual(response.status_code, 200)

        response_data = response.json()

        self.assertEqual(response_data.get("pathParameters"), {"id": "4", "user": "jacob"})

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_forward_headers_are_added_to_event(self):
        """
        Test the Forwarding Headers exist in the Api Event to Lambda
        """
        response = requests.get(self.url + "/id/4", timeout=300)

        response_data = response.json()

        self.assertEqual(response_data.get("headers").get("X-Forwarded-Proto"), "http")
        self.assertEqual(response_data.get("multiValueHeaders").get("X-Forwarded-Proto"), ["http"])
        self.assertEqual(response_data.get("headers").get("X-Forwarded-Port"), self.port)
        self.assertEqual(response_data.get("multiValueHeaders").get("X-Forwarded-Port"), [self.port])


class TestServiceRequestsWithHttpApi(StartApiIntegBaseClass):
    """
    Test Class centered around the different requests that can happen; specifically testing the change
    in format for mulivalue query parameters in payload format v2 (HTTP APIs)
    """

    template_path = "/testdata/start_api/swagger-template-http-api.yaml"

    def setUp(self):
        self.url = "http://127.0.0.1:{}".format(self.port)

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_request_with_multi_value_headers(self):
        response = requests.get(
            self.url + "/echoeventbody",
            headers={"Content-Type": "application/x-www-form-urlencoded, image/gif"},
            timeout=300,
        )

        self.assertEqual(response.status_code, 200)
        response_data = response.json()
        self.assertEqual(response_data.get("version"), "2.0")
        self.assertIsNone(response_data.get("multiValueHeaders"))
        self.assertEqual(
            response_data.get("headers").get("Content-Type"), "application/x-www-form-urlencoded, image/gif"
        )

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_request_with_list_of_query_params(self):
        """
        Query params given should be put into the Event to Lambda
        """
        response = requests.get(self.url + "/echoeventbody", params={"key": ["value", "value2"]}, timeout=300)

        self.assertEqual(response.status_code, 200)

        response_data = response.json()

        self.assertEqual(response_data.get("version"), "2.0")
        self.assertEqual(response_data.get("queryStringParameters"), {"key": "value,value2"})
        self.assertIsNone(response_data.get("multiValueQueryStringParameters"))


class TestStartApiWithStage(StartApiIntegBaseClass):
    """
    Test Class centered around the different responses that can happen in Lambda and pass through start-api
    """

    template_path = "/testdata/start_api/template.yaml"

    def setUp(self):
        self.url = "http://127.0.0.1:{}".format(self.port)

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_default_stage_name(self):
        response = requests.get(self.url + "/echoeventbody", timeout=300)

        self.assertEqual(response.status_code, 200)

        response_data = response.json()

        self.assertEqual(response_data.get("requestContext", {}).get("stage"), "Prod")

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_global_stage_variables(self):
        response = requests.get(self.url + "/echoeventbody", timeout=300)

        self.assertEqual(response.status_code, 200)

        response_data = response.json()

        self.assertEqual(response_data.get("stageVariables"), {"VarName": "varValue"})


class TestStartApiWithStageAndSwagger(StartApiIntegBaseClass):
    """
    Test Class centered around the different responses that can happen in Lambda and pass through start-api
    """

    template_path = "/testdata/start_api/swagger-template.yaml"

    def setUp(self):
        self.url = "http://127.0.0.1:{}".format(self.port)

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_swagger_stage_name(self):
        response = requests.get(self.url + "/echoeventbody", timeout=300)

        self.assertEqual(response.status_code, 200)

        response_data = response.json()
        self.assertEqual(response_data.get("requestContext", {}).get("stage"), "dev")

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_swagger_stage_variable(self):
        response = requests.get(self.url + "/echoeventbody", timeout=300)

        self.assertEqual(response.status_code, 200)

        response_data = response.json()
        self.assertEqual(response_data.get("stageVariables"), {"VarName": "varValue"})


class TestStartApiWithStageAndSwaggerWithHttpApi(StartApiIntegBaseClass):
    """
    Test Class centered around the different responses that can happen in Lambda and pass through start-api
    """

    template_path = "/testdata/start_api/swagger-template-http-api.yaml"

    def setUp(self):
        self.url = "http://127.0.0.1:{}".format(self.port)

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_swagger_stage_name_httpapi(self):
        response = requests.get(self.url + "/httpapi-echoeventbody", timeout=300)

        self.assertEqual(response.status_code, 200)

        response_data = response.json()
        self.assertEqual(response_data.get("requestContext", {}).get("stage"), "dev-http")

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_swagger_stage_variable_httpapi(self):
        response = requests.get(self.url + "/httpapi-echoeventbody", timeout=300)

        self.assertEqual(response.status_code, 200)

        response_data = response.json()
        self.assertEqual(response_data.get("stageVariables"), {"VarNameHttpApi": "varValueV2"})


class TestPayloadVersionWithStageAndSwaggerWithHttpApi(StartApiIntegBaseClass):
    template_path = "/testdata/start_api/swagger-template-http-api.yaml"

    def setUp(self):
        self.url = "http://127.0.0.1:{}".format(self.port)

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_payload_version_v1_swagger_inline_httpapi(self):
        response = requests.get(self.url + "/httpapi-payload-format-v1", timeout=300)

        self.assertEqual(response.status_code, 200)
        response_data = response.json()
        self.assertEqual(response_data.get("version", {}), "1.0")

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_payload_version_v2_swagger_inline_httpapi(self):
        response = requests.get(self.url + "/httpapi-payload-format-v2", timeout=300)

        self.assertEqual(response.status_code, 200)
        response_data = response.json()
        self.assertEqual(response_data.get("version", {}), "2.0")

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_payload_version_v1_property_httpapi(self):
        response = requests.get(self.url + "/httpapi-payload-format-v1-property", timeout=300)

        self.assertEqual(response.status_code, 200)
        response_data = response.json()
        print(response_data)
        self.assertEqual(response_data.get("version", {}), "1.0")


class TestOptionsHandler(StartApiIntegBaseClass):
    """
    Test to check that an OPTIONS handler is invoked
    """

    template_path = "/testdata/start_api/options-handler-template.yml"

    def setUp(self):
        self.url = "http://127.0.0.1:{}".format(self.port)

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_options_handler(self):
        """
        This tests that a template's OPTIONS handler is invoked
        """
        response = requests.options(self.url + "/optionshandler", timeout=300)

        self.assertEqual(response.status_code, 204)


class TestServiceCorsSwaggerRequests(StartApiIntegBaseClass):
    """
    Test to check that the correct headers are being added with Cors with swagger code
    """

    template_path = "/testdata/start_api/swagger-template.yaml"
    binary_data_file = "testdata/start_api/binarydata.gif"

    def setUp(self):
        self.url = "http://127.0.0.1:{}".format(self.port)

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_cors_swagger_options(self):
        """
        This tests that the Cors are added to option requests in the swagger template
        """
        response = requests.options(self.url + "/echobase64eventbody", timeout=300)

        self.assertEqual(response.status_code, 200)

        self.assertEqual(response.headers.get("Access-Control-Allow-Origin"), "*")
        self.assertEqual(response.headers.get("Access-Control-Allow-Headers"), "origin, x-requested-with")
        self.assertEqual(response.headers.get("Access-Control-Allow-Methods"), "GET,OPTIONS")
        self.assertEqual(response.headers.get("Access-Control-Allow-Credentials"), "true")
        self.assertEqual(response.headers.get("Access-Control-Max-Age"), "510")


class TestServiceCorsSwaggerRequestsWithHttpApi(StartApiIntegBaseClass):
    """
    Test to check that the correct headers are being added with Cors with swagger code
    """

    template_path = "/testdata/start_api/swagger-template-http-api.yaml"
    binary_data_file = "testdata/start_api/binarydata.gif"

    def setUp(self):
        self.url = "http://127.0.0.1:{}".format(self.port)

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_cors_swagger_options_httpapi(self):
        """
        This tests that the Cors are added to option requests in the swagger template
        """
        response = requests.options(self.url + "/httpapi-echobase64eventbody", timeout=300)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get("Access-Control-Allow-Origin"), "*")
        self.assertEqual(response.headers.get("Access-Control-Allow-Headers"), "origin")
        self.assertEqual(response.headers.get("Access-Control-Allow-Methods"), "GET,OPTIONS,POST")
        self.assertEqual(response.headers.get("Access-Control-Allow-Credentials"), "true")
        self.assertEqual(response.headers.get("Access-Control-Max-Age"), "42")


class TestServiceCorsGlobalRequests(StartApiIntegBaseClass):
    """
    Test to check that the correct headers are being added with Cors with the global property
    """

    template_path = "/testdata/start_api/template.yaml"

    def setUp(self):
        self.url = "http://127.0.0.1:{}".format(self.port)

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_cors_global(self):
        """
        This tests that the Cors are added to options requests when the global property is set
        """
        response = requests.options(self.url + "/echobase64eventbody", timeout=300)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get("Access-Control-Allow-Origin"), "*")
        self.assertEqual(response.headers.get("Access-Control-Allow-Headers"), None)
        self.assertEqual(response.headers.get("Access-Control-Allow-Methods"), ",".join(sorted(Route.ANY_HTTP_METHODS)))
        self.assertEqual(response.headers.get("Access-Control-Allow-Credentials"), None)
        self.assertEqual(response.headers.get("Access-Control-Max-Age"), None)

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_cors_global_get(self):
        """
        This tests that the Cors are added to post requests when the global property is set
        """
        response = requests.get(self.url + "/onlysetstatuscode", timeout=300)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode("utf-8"), "")
        self.assertEqual(response.headers.get("Content-Type"), "application/json")
        self.assertEqual(response.headers.get("Access-Control-Allow-Origin"), None)
        self.assertEqual(response.headers.get("Access-Control-Allow-Headers"), None)
        self.assertEqual(response.headers.get("Access-Control-Allow-Methods"), None)
        self.assertEqual(response.headers.get("Access-Control-Allow-Credentials"), None)
        self.assertEqual(response.headers.get("Access-Control-Max-Age"), None)


class TestStartApiWithCloudFormationStage(StartApiIntegBaseClass):
    """
    Test Class centered around the different responses that can happen in Lambda and pass through start-api
    """

    template_path = "/testdata/start_api/swagger-rest-api-template.yaml"

    def setUp(self):
        self.url = "http://127.0.0.1:{}".format(self.port)

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_default_stage_name(self):
        response = requests.get(self.url + "/echoeventbody", timeout=300)

        self.assertEqual(response.status_code, 200)

        response_data = response.json()
        self.assertEqual(response_data.get("requestContext", {}).get("stage"), "Dev")

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_global_stage_variables(self):
        response = requests.get(self.url + "/echoeventbody", timeout=300)

        self.assertEqual(response.status_code, 200)

        response_data = response.json()

        self.assertEqual(response_data.get("stageVariables"), {"Stack": "Dev"})


class TestStartApiWithMethodsAndResources(StartApiIntegBaseClass):
    template_path = "/testdata/start_api/methods-resources-api-template.yaml"
    binary_data_file = "testdata/start_api/binarydata.gif"

    def setUp(self):
        self.url = "http://127.0.0.1:{}".format(self.port)

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_get_call_with_path_setup_with_any_swagger(self):
        """
        Get Request to a path that was defined as ANY in SAM through Swagger
        """
        response = requests.get(self.url + "/root/anyandall", timeout=300)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"hello": "world"})

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_post_call_with_path_setup_with_any_swagger(self):
        """
        Post Request to a path that was defined as ANY in SAM through Swagger
        """
        response = requests.post(self.url + "/root/anyandall", json={}, timeout=300)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"hello": "world"})

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_put_call_with_path_setup_with_any_swagger(self):
        """
        Put Request to a path that was defined as ANY in SAM through Swagger
        """
        response = requests.put(self.url + "/root/anyandall", json={}, timeout=300)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"hello": "world"})

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_head_call_with_path_setup_with_any_swagger(self):
        """
        Head Request to a path that was defined as ANY in SAM through Swagger
        """
        response = requests.head(self.url + "/root/anyandall", timeout=300)

        self.assertEqual(response.status_code, 200)

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_delete_call_with_path_setup_with_any_swagger(self):
        """
        Delete Request to a path that was defined as ANY in SAM through Swagger
        """
        response = requests.delete(self.url + "/root/anyandall", timeout=300)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"hello": "world"})

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_options_call_with_path_setup_with_any_swagger(self):
        """
        Options Request to a path that was defined as ANY in SAM through Swagger
        """
        response = requests.options(self.url + "/root/anyandall", timeout=300)

        self.assertEqual(response.status_code, 200)

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_patch_call_with_path_setup_with_any_swagger(self):
        """
        Patch Request to a path that was defined as ANY in SAM through Swagger
        """
        response = requests.patch(self.url + "/root/anyandall", timeout=300)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"hello": "world"})

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_function_not_defined_in_template(self):
        response = requests.get(self.url + "/root/nofunctionfound", timeout=300)

        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.json(), {"message": "No function defined for resource method"})

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_lambda_function_resource_is_reachable(self):
        response = requests.get(self.url + "/root/nonserverlessfunction", timeout=300)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"hello": "world"})

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_binary_request(self):
        """
        This tests that the service can accept and invoke a lambda when given binary data in a request
        """
        input_data = self.get_binary_data(self.binary_data_file)
        response = requests.post(
            self.url + "/root/echobase64eventbody", headers={"Content-Type": "image/gif"}, data=input_data, timeout=300
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get("Content-Type"), "image/gif")
        self.assertEqual(response.content, input_data)

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_binary_response(self):
        """
        Binary data is returned correctly
        """
        expected = self.get_binary_data(self.binary_data_file)

        response = requests.get(self.url + "/root/base64response", timeout=300)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get("Content-Type"), "image/gif")
        self.assertEqual(response.content, expected)

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_proxy_response(self):
        """
        Binary data is returned correctly
        """
        response = requests.get(self.url + "/root/v1/test", timeout=300)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"hello": "world"})


class TestCDKApiGateway(StartApiIntegBaseClass):
    template_path = "/testdata/start_api/cdk-sample-output.yaml"

    def setUp(self):
        self.url = "http://127.0.0.1:{}".format(self.port)

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_get_with_cdk(self):
        """
        Get Request to a path that was defined as ANY in SAM through Swagger
        """
        response = requests.get(self.url + "/hello-world", timeout=300)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"hello": "world"})


class TestServerlessApiGateway(StartApiIntegBaseClass):
    template_path = "/testdata/start_api/serverless-sample-output.yaml"

    def setUp(self):
        self.url = "http://127.0.0.1:{}".format(self.port)

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_get_with_serverless(self):
        """
        Get Request to a path that was defined as ANY in SAM through Swagger
        """
        response = requests.get(self.url + "/hello-world", timeout=300)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"hello": "world"})


class TestSwaggerIncludedFromSeparateFile(StartApiIntegBaseClass):
    template_path = "/testdata/start_api/template-with-included-swagger.yaml"

    def setUp(self):
        self.url = "http://127.0.0.1:{}".format(self.port)

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_swagger_was_tranformed_and_api_is_reachable(self):
        response = requests.patch(self.url + "/anyandall", timeout=300)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"hello": "world"})


class TestUnresolvedCorsIntrinsic(StartApiIntegBaseClass):
    template_path = "/testdata/start_api/template-with-unresolved-intrinsic-in-cors.yaml"

    def setUp(self):
        self.url = "http://127.0.0.1:{}".format(self.port)

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_lambda_is_reachable_when_cors_is_an_unresolved_intrinsic(self):
        response = requests.patch(self.url + "/anyandall", timeout=300)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"hello": "world"})


class TestCFNTemplateQuickCreatedHttpApiWithDefaultRoute(StartApiIntegBaseClass):
    template_path = "/testdata/start_api/cfn-quick-created-http-api-with-default-route.yaml"

    def setUp(self):
        self.url = "http://127.0.0.1:{}".format(self.port)

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_default_route_is_created_and_api_is_reachable(self):
        response = requests.patch(self.url + "/anypath/anypath", timeout=300)

        self.assertEqual(response.status_code, 200)
        response_data = response.json()
        self.assertEqual(response_data.get("version", {}), "2.0")
        self.assertEqual(response_data.get("routeKey", {}), "$default")
        self.assertIsNone(response_data.get("multiValueHeaders"))
        self.assertIsNotNone(response_data.get("cookies"))

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_cors_options(self):
        """
        This tests that the Cors are added to option requests in the swagger template
        """
        response = requests.options(self.url + "/anypath/anypath", timeout=300)

        self.assertEqual(response.status_code, 200)

        self.assertEqual(response.headers.get("Access-Control-Allow-Origin"), "https://example.com")
        self.assertEqual(response.headers.get("Access-Control-Allow-Headers"), "x-apigateway-header")
        self.assertEqual(response.headers.get("Access-Control-Allow-Methods"), "GET,OPTIONS")
        self.assertEqual(response.headers.get("Access-Control-Allow-Credentials"), "true")
        self.assertEqual(response.headers.get("Access-Control-Max-Age"), "600")


@parameterized_class(
    ("template_path",),
    [
        ("/testdata/start_api/cfn-http-api-with-normal-and-default-routes.yaml",),
        ("/testdata/start_api/nested-templates/cfn-http-api-with-normal-and-default-routes-parent.yaml",),
    ],
)
class TestCFNTemplateHttpApiWithNormalAndDefaultRoutes(StartApiIntegBaseClass):
    def setUp(self):
        self.url = "http://127.0.0.1:{}".format(self.port)

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_default_route_is_created_and_api_is_reachable(self):
        response = requests.post(self.url + "/anypath/anypath", timeout=300)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"hello": "world"})

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_normal_route_is_created_and_api_is_reachable_and_payload_version_is_1(self):
        response = requests.get(self.url + "/echoeventbody", timeout=300)

        self.assertEqual(response.status_code, 200)
        response_data = response.json()
        self.assertEqual(response_data.get("version", {}), "1.0")
        self.assertIsNotNone(response_data.get("multiValueHeaders"))
        self.assertIsNone(response_data.get("cookies"))


class TestCFNTemplateQuickCreatedHttpApiWithOneRoute(StartApiIntegBaseClass):
    template_path = "/testdata/start_api/cfn-quick-created-http-api-with-one-route.yaml"

    def setUp(self):
        self.url = "http://127.0.0.1:{}".format(self.port)

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_route_is_created_and_api_is_reachable_and_default_payload_version_is_2(self):
        response = requests.get(self.url + "/echoeventbody", timeout=300)

        self.assertEqual(response.status_code, 200)
        response_data = response.json()
        self.assertEqual(response_data.get("version", {}), "2.0")
        self.assertEqual(response_data.get("routeKey", {}), "GET /echoeventbody")
        self.assertIsNone(response_data.get("multiValueHeaders"))
        self.assertIsNotNone(response_data.get("cookies"))

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_default_stage_name(self):
        response = requests.get(self.url + "/echoeventbody", timeout=300)

        self.assertEqual(response.status_code, 200)
        response_data = response.json()
        self.assertEqual(response_data.get("requestContext", {}).get("stage"), "$default")


class TestServerlessTemplateWithRestApiAndHttpApiGateways(StartApiIntegBaseClass):
    template_path = "/testdata/start_api/template-rest-and-http-apis.yaml"

    def setUp(self):
        self.url = "http://127.0.0.1:{}".format(self.port)

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_http_api_is_reachable(self):
        response = requests.get(self.url + "/http-api", timeout=300)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"hello": "world"})

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_rest_api_is_reachable(self):
        response = requests.get(self.url + "/rest-api", timeout=300)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"hello": "world"})


@parameterized_class(
    ("template_path",),
    [
        ("/testdata/start_api/cfn-http-api-and-rest-api-gateways.yaml",),
        ("/testdata/start_api/nested-templates/cfn-http-api-and-rest-api-gateways-parent.yaml",),
    ],
)
class TestCFNTemplateWithRestApiAndHttpApiGateways(StartApiIntegBaseClass):
    template_path = "/testdata/start_api/cfn-http-api-and-rest-api-gateways.yaml"

    def setUp(self):
        self.url = "http://127.0.0.1:{}".format(self.port)

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_http_api_is_reachable(self):
        response = requests.get(self.url + "/http-api", timeout=300)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"hello": "world"})

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_http_api_with_operation_name_is_reachable(self):
        response = requests.get(self.url + "/http-api-with-operation-name", timeout=300)

        self.assertEqual(response.status_code, 200)
        response_data = response.json()
        # operationName or operationId shouldn't be processed by Httpapi
        request_context_keys = [key.lower() for key in response_data.get("requestContext", {}).keys()]
        self.assertTrue("operationid" not in request_context_keys)
        self.assertTrue("operationname" not in request_context_keys)

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_rest_api_is_reachable(self):
        response = requests.get(self.url + "/rest-api", timeout=300)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"hello": "world"})

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_rest_api_with_operation_name_is_reachable(self):
        response = requests.get(self.url + "/rest-api-with-operation-name", timeout=300)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"operation_name": "MyOperationName"})


class TestCFNTemplateHttpApiWithSwaggerBody(StartApiIntegBaseClass):
    template_path = "/testdata/start_api/cfn-http-api-with-swagger-body.yaml"

    def setUp(self):
        self.url = "http://127.0.0.1:{}".format(self.port)

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_swagger_got_parsed_and_api_is_reachable_and_payload_version_is_2(self):
        response = requests.get(self.url + "/echoeventbody", timeout=300)

        self.assertEqual(response.status_code, 200)
        response_data = response.json()
        self.assertEqual(response_data.get("version", {}), "2.0")
        self.assertIsNone(response_data.get("multiValueHeaders"))
        self.assertIsNotNone(response_data.get("cookies"))
        # operationName or operationId shouldn't be processed by Httpapi swaggers
        request_context_keys = [key.lower() for key in response_data.get("requestContext", {}).keys()]
        self.assertTrue("operationid" not in request_context_keys)
        self.assertTrue("operationname" not in request_context_keys)


class TestWarmContainersBaseClass(StartApiIntegBaseClass):
    def setUp(self):
        self.url = "http://127.0.0.1:{}".format(self.port)

    def count_running_containers(self):
        running_containers = 0
        for container in self.docker_client.containers.list():
            _, output = container.exec_run(["bash", "-c", "'printenv'"])
            if f"MODE={self.mode_env_variable}" in str(output):
                running_containers += 1
        return running_containers


@parameterized_class(
    ("template_path",),
    [
        ("/testdata/start_api/template-warm-containers.yaml",),
        ("/testdata/start_api/cdk/template-cdk-warm-container.yaml",),
    ],
)
class TestWarmContainers(TestWarmContainersBaseClass):
    container_mode = ContainersInitializationMode.EAGER.value
    mode_env_variable = str(uuid.uuid4())
    parameter_overrides = {"ModeEnvVariable": mode_env_variable}

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_can_invoke_lambda_function_successfully(self):
        response = requests.post(self.url + "/id", timeout=300)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"hello": "world"})


@parameterized_class(
    ("template_path",),
    [
        ("/testdata/start_api/template-warm-containers.yaml",),
        ("/testdata/start_api/cdk/template-cdk-warm-container.yaml",),
    ],
)
class TestWarmContainersInitialization(TestWarmContainersBaseClass):
    container_mode = ContainersInitializationMode.EAGER.value
    mode_env_variable = str(uuid.uuid4())
    parameter_overrides = {"ModeEnvVariable": mode_env_variable}

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_all_containers_are_initialized_before_any_invoke(self):
        initiated_containers = self.count_running_containers()
        # validate that there a container initialized for each lambda function
        self.assertEqual(initiated_containers, 2)


@parameterized_class(
    ("template_path",),
    [
        ("/testdata/start_api/template-warm-containers.yaml",),
        ("/testdata/start_api/cdk/template-cdk-warm-container.yaml",),
    ],
)
class TestWarmContainersMultipleInvoke(TestWarmContainersBaseClass):
    container_mode = ContainersInitializationMode.EAGER.value
    mode_env_variable = str(uuid.uuid4())
    parameter_overrides = {"ModeEnvVariable": mode_env_variable}

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_no_new_created_containers_after_lambda_function_invoke(self):
        initiated_containers_before_invoking_any_function = self.count_running_containers()
        requests.post(self.url + "/id", timeout=300)
        initiated_containers = self.count_running_containers()

        # validate that no new containers got created
        self.assertEqual(initiated_containers, initiated_containers_before_invoking_any_function)


@parameterized_class(
    ("template_path",),
    [
        ("/testdata/start_api/template-warm-containers.yaml",),
        ("/testdata/start_api/cdk/template-cdk-warm-container.yaml",),
    ],
)
class TestLazyContainers(TestWarmContainersBaseClass):
    container_mode = ContainersInitializationMode.LAZY.value
    mode_env_variable = str(uuid.uuid4())
    parameter_overrides = {"ModeEnvVariable": mode_env_variable}

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_can_invoke_lambda_function_successfully(self):
        response = requests.post(self.url + "/id", timeout=300)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"hello": "world"})


@parameterized_class(
    ("template_path",),
    [
        ("/testdata/start_api/template-warm-containers.yaml",),
        ("/testdata/start_api/cdk/template-cdk-warm-container.yaml",),
    ],
)
class TestLazyContainersInitialization(TestWarmContainersBaseClass):
    container_mode = ContainersInitializationMode.LAZY.value
    mode_env_variable = str(uuid.uuid4())
    parameter_overrides = {"ModeEnvVariable": mode_env_variable}

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_no_container_is_initialized_before_any_invoke(self):
        initiated_containers = self.count_running_containers()

        # no container is initialized
        self.assertEqual(initiated_containers, 0)


@parameterized_class(
    ("template_path",),
    [
        ("/testdata/start_api/template-warm-containers.yaml",),
        ("/testdata/start_api/cdk/template-cdk-warm-container.yaml",),
    ],
)
class TestLazyContainersMultipleInvoke(TestWarmContainersBaseClass):
    container_mode = ContainersInitializationMode.LAZY.value
    mode_env_variable = str(uuid.uuid4())
    parameter_overrides = {"ModeEnvVariable": mode_env_variable}

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_only_one_new_created_containers_after_lambda_function_invoke(self):
        initiated_containers_before_any_invoke = self.count_running_containers()
        requests.post(self.url + "/id", timeout=300)
        initiated_containers = self.count_running_containers()

        # only one container is initialized
        self.assertEqual(initiated_containers, initiated_containers_before_any_invoke + 1)


class TestImagePackageType(StartApiIntegBaseClass):
    template_path = "/testdata/start_api/image_package_type/template.yaml"
    build_before_invoke = True
    tag = f"python-{random.randint(1000,2000)}"
    build_overrides = {"Tag": tag}
    parameter_overrides = {"ImageUri": f"helloworldfunction:{tag}"}

    def setUp(self):
        self.url = "http://127.0.0.1:{}".format(self.port)

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_can_invoke_lambda_function_successfully(self):
        response = requests.get(self.url + "/hello", timeout=300)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"hello": "world"})


class TestImagePackageTypeWithEagerWarmContainersMode(StartApiIntegBaseClass):
    template_path = "/testdata/start_api/image_package_type/template.yaml"
    container_mode = ContainersInitializationMode.EAGER.value
    build_before_invoke = True
    tag = f"python-{random.randint(1000,2000)}"
    build_overrides = {"Tag": tag}
    parameter_overrides = {"ImageUri": f"helloworldfunction:{tag}"}

    def setUp(self):
        self.url = "http://127.0.0.1:{}".format(self.port)

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_can_invoke_lambda_function_successfully(self):
        response = requests.get(self.url + "/hello", timeout=300)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"hello": "world"})


class TestImagePackageTypeWithEagerLazyContainersMode(StartApiIntegBaseClass):
    template_path = "/testdata/start_api/image_package_type/template.yaml"
    container_mode = ContainersInitializationMode.LAZY.value
    build_before_invoke = True
    tag = f"python-{random.randint(1000,2000)}"
    build_overrides = {"Tag": tag}
    parameter_overrides = {"ImageUri": f"helloworldfunction:{tag}"}

    def setUp(self):
        self.url = "http://127.0.0.1:{}".format(self.port)

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_can_invoke_lambda_function_successfully(self):
        response = requests.get(self.url + "/hello", timeout=300)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"hello": "world"})


class TestWatchingZipWarmContainers(WatchWarmContainersIntegBaseClass):
    template_content = """AWSTemplateFormatVersion : '2010-09-09'
Transform: AWS::Serverless-2016-10-31    
Resources:
  HelloWorldFunction:
    Type: AWS::Serverless::Function
    Properties:
      Handler: main.handler
      Runtime: python3.9
      CodeUri: .
      Timeout: 600
      Events:
        PathWithPathParams:
          Type: Api
          Properties:
            Method: GET
            Path: /hello
    """
    code_content = """import json

def handler(event, context):
    return {"statusCode": 200, "body": json.dumps({"hello": "world"})}
    """
    code_content_2 = """import json

def handler(event, context):
    return {"statusCode": 200, "body": json.dumps({"hello": "world2"})}
    """
    docker_file_content = ""
    container_mode = ContainersInitializationMode.EAGER.value

    def setUp(self):
        self.url = "http://127.0.0.1:{}".format(self.port)

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_changed_code_got_observed_and_loaded(self):
        response = requests.get(self.url + "/hello", timeout=300)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"hello": "world"})

        self._write_file_content(self.code_path, self.code_content_2)
        # wait till SAM got notified that the source code got changed
        sleep(2)
        response = requests.get(self.url + "/hello", timeout=300)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"hello": "world2"})


class TestWatchingTemplateChangesLambdaFunctionHandlerChanged(WatchWarmContainersIntegBaseClass):
    template_content = """AWSTemplateFormatVersion : '2010-09-09'
Transform: AWS::Serverless-2016-10-31    
Resources:
  HelloWorldFunction:
    Type: AWS::Serverless::Function
    Properties:
      Handler: main.handler
      Runtime: python3.9
      CodeUri: .
      Timeout: 600
      Events:
        PathWithPathParams:
          Type: Api
          Properties:
            Method: GET
            Path: /hello
    """

    template_content_2 = """AWSTemplateFormatVersion : '2010-09-09'
Transform: AWS::Serverless-2016-10-31    
Resources:
  HelloWorldFunction:
    Type: AWS::Serverless::Function
    Properties:
      Handler: main.handler2
      Runtime: python3.9
      CodeUri: .
      Timeout: 600
      Events:
        PathWithPathParams:
          Type: Api
          Properties:
            Method: GET
            Path: /hello
    """
    code_content = """import json

def handler(event, context):
    return {"statusCode": 200, "body": json.dumps({"hello": "world"})}
    
def handler2(event, context):
    return {"statusCode": 200, "body": json.dumps({"hello": "world2"})}
    """

    docker_file_content = ""
    container_mode = ContainersInitializationMode.EAGER.value

    def setUp(self):
        self.url = "http://127.0.0.1:{}".format(self.port)

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_changed_code_got_observed_and_loaded(self):
        response = requests.get(self.url + "/hello", timeout=300)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"hello": "world"})

        self._write_file_content(self.template_path, self.template_content_2)
        # wait till SAM got notified that the source code got changed
        sleep(2)
        response = requests.get(self.url + "/hello", timeout=300)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"hello": "world2"})


class TestWatchingTemplateChangesLambdaFunctionCodeUriChanged(WatchWarmContainersIntegBaseClass):
    template_content = """AWSTemplateFormatVersion : '2010-09-09'
Transform: AWS::Serverless-2016-10-31    
Resources:
  HelloWorldFunction:
    Type: AWS::Serverless::Function
    Properties:
      Handler: main.handler
      Runtime: python3.7
      CodeUri: .
      Timeout: 600
      Events:
        PathWithPathParams:
          Type: Api
          Properties:
            Method: GET
            Path: /hello
    """

    template_content_2 = """AWSTemplateFormatVersion : '2010-09-09'
Transform: AWS::Serverless-2016-10-31    
Resources:
  HelloWorldFunction:
    Type: AWS::Serverless::Function
    Properties:
      Handler: main2.handler
      Runtime: python3.7
      CodeUri: dir
      Timeout: 600
      Events:
        PathWithPathParams:
          Type: Api
          Properties:
            Method: GET
            Path: /hello
    """
    code_content = """import json

def handler(event, context):
    return {"statusCode": 200, "body": json.dumps({"hello": "world"})}
    """
    code_content_2 = """import json

def handler(event, context):
    return {"statusCode": 200, "body": json.dumps({"hello": "world2"})}
        """

    docker_file_content = ""
    container_mode = ContainersInitializationMode.EAGER.value

    def setUp(self):
        self.url = "http://127.0.0.1:{}".format(self.port)

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_changed_code_got_observed_and_loaded(self):
        response = requests.get(self.url + "/hello", timeout=300)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"hello": "world"})

        self._write_file_content(self.template_path, self.template_content_2)
        self._write_file_content(self.code_path2, self.code_content_2)
        # wait till SAM got notified that the source code got changed
        sleep(2)
        response = requests.get(self.url + "/hello", timeout=300)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"hello": "world2"})


class TestWatchingImageWarmContainers(WatchWarmContainersIntegBaseClass):
    template_content = """AWSTemplateFormatVersion : '2010-09-09'
Transform: AWS::Serverless-2016-10-31    
Parameters:
  Tag:
    Type: String
  ImageUri:
    Type: String
Resources:
  HelloWorldFunction:
    Type: AWS::Serverless::Function
    Properties:
      PackageType: Image
      ImageConfig:
        Command:
          - main.handler
        Timeout: 600
      ImageUri: !Ref ImageUri
      Events:
        PathWithPathParams:
          Type: Api
          Properties:
            Method: GET
            Path: /hello
    Metadata:
      DockerTag: !Ref Tag
      DockerContext: .
      Dockerfile: Dockerfile
        """
    code_content = """import json

def handler(event, context):
    return {"statusCode": 200, "body": json.dumps({"hello": "world"})}"""
    code_content_2 = """import json

def handler(event, context):
    return {"statusCode": 200, "body": json.dumps({"hello": "world2"})}"""
    docker_file_content = """FROM public.ecr.aws/lambda/python:3.7
COPY main.py ./"""
    container_mode = ContainersInitializationMode.EAGER.value
    build_before_invoke = True
    tag = f"python-{random.randint(1000, 2000)}"
    build_overrides = {"Tag": tag}
    parameter_overrides = {"ImageUri": f"helloworldfunction:{tag}"}

    def setUp(self):
        self.url = "http://127.0.0.1:{}".format(self.port)

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=6000, method="thread")
    def test_changed_code_got_observed_and_loaded(self):
        response = requests.get(self.url + "/hello", timeout=300)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"hello": "world"})

        self._write_file_content(self.code_path, self.code_content_2)
        self.build()
        # wait till SAM got notified that the image got changed
        sleep(2)
        response = requests.get(self.url + "/hello", timeout=300)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"hello": "world2"})


class TestWatchingTemplateChangesImageDockerFileChangedLocation(WatchWarmContainersIntegBaseClass):
    template_content = """AWSTemplateFormatVersion : '2010-09-09'
Transform: AWS::Serverless-2016-10-31    
Parameters:
  Tag:
    Type: String
  ImageUri:
    Type: String
Resources:
  HelloWorldFunction:
    Type: AWS::Serverless::Function
    Properties:
      PackageType: Image
      ImageConfig:
        Command:
          - main.handler
        Timeout: 600
      ImageUri: !Ref ImageUri
      Events:
        PathWithPathParams:
          Type: Api
          Properties:
            Method: GET
            Path: /hello
    Metadata:
      DockerTag: !Ref Tag
      DockerContext: .
      Dockerfile: Dockerfile
        """
    template_content_2 = """AWSTemplateFormatVersion : '2010-09-09'
Transform: AWS::Serverless-2016-10-31    
Parameters:
  Tag:
    Type: String
  ImageUri:
    Type: String
Resources:
  HelloWorldFunction:
    Type: AWS::Serverless::Function
    Properties:
      PackageType: Image
      ImageConfig:
        Command:
          - main.handler
        Timeout: 600
      ImageUri: !Ref ImageUri
      Events:
        PathWithPathParams:
          Type: Api
          Properties:
            Method: GET
            Path: /hello
    Metadata:
      DockerTag: !Ref Tag
      DockerContext: .
      Dockerfile: Dockerfile2
        """
    code_content = """import json

def handler(event, context):
    return {"statusCode": 200, "body": json.dumps({"hello": "world"})}"""
    code_content_2 = """import json

def handler(event, context):
    return {"statusCode": 200, "body": json.dumps({"hello": "world2"})}"""
    docker_file_content = """FROM public.ecr.aws/lambda/python:3.7
COPY main.py ./"""
    container_mode = ContainersInitializationMode.EAGER.value
    build_before_invoke = True
    tag = f"python-{random.randint(1000, 2000)}"
    build_overrides = {"Tag": tag}
    parameter_overrides = {"ImageUri": f"helloworldfunction:{tag}"}

    def setUp(self):
        self.url = "http://127.0.0.1:{}".format(self.port)

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=6000, method="thread")
    def test_changed_code_got_observed_and_loaded(self):
        response = requests.get(self.url + "/hello", timeout=300)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"hello": "world"})

        self._write_file_content(self.template_path, self.template_content_2)
        self._write_file_content(self.code_path, self.code_content_2)
        self._write_file_content(self.docker_file_path2, self.docker_file_content)
        self.build()
        # wait till SAM got notified that the image got changed
        sleep(2)
        response = requests.get(self.url + "/hello", timeout=300)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"hello": "world2"})


class TestWatchingZipLazyContainers(WatchWarmContainersIntegBaseClass):
    template_content = """AWSTemplateFormatVersion : '2010-09-09'
Transform: AWS::Serverless-2016-10-31    
Resources:
  HelloWorldFunction:
    Type: AWS::Serverless::Function
    Properties:
      Handler: main.handler
      Runtime: python3.9
      CodeUri: .
      Timeout: 600
      Events:
        PathWithPathParams:
          Type: Api
          Properties:
            Method: GET
            Path: /hello
    """
    code_content = """import json

def handler(event, context):
    return {"statusCode": 200, "body": json.dumps({"hello": "world"})}
    """
    code_content_2 = """import json

def handler(event, context):
    return {"statusCode": 200, "body": json.dumps({"hello": "world2"})}
    """
    docker_file_content = ""
    container_mode = ContainersInitializationMode.LAZY.value

    def setUp(self):
        self.url = "http://127.0.0.1:{}".format(self.port)

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_changed_code_got_observed_and_loaded(self):
        response = requests.get(self.url + "/hello", timeout=300)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"hello": "world"})

        self._write_file_content(self.code_path, self.code_content_2)
        # wait till SAM got notified that the source code got changed
        sleep(2)
        response = requests.get(self.url + "/hello", timeout=300)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"hello": "world2"})


class TestWatchingImageLazyContainers(WatchWarmContainersIntegBaseClass):
    template_content = """AWSTemplateFormatVersion : '2010-09-09'
Transform: AWS::Serverless-2016-10-31    
Parameters:
  Tag:
    Type: String
  ImageUri:
    Type: String
Resources:
  HelloWorldFunction:
    Type: AWS::Serverless::Function
    Properties:
      PackageType: Image
      ImageConfig:
        Command:
          - main.handler
        Timeout: 600
      ImageUri: !Ref ImageUri
      Events:
        PathWithPathParams:
          Type: Api
          Properties:
            Method: GET
            Path: /hello
    Metadata:
      DockerTag: !Ref Tag
      DockerContext: .
      Dockerfile: Dockerfile
        """
    code_content = """import json

def handler(event, context):
    return {"statusCode": 200, "body": json.dumps({"hello": "world"})}"""
    code_content_2 = """import json

def handler(event, context):
    return {"statusCode": 200, "body": json.dumps({"hello": "world2"})}"""
    docker_file_content = """FROM public.ecr.aws/lambda/python:3.7
COPY main.py ./"""
    container_mode = ContainersInitializationMode.LAZY.value
    build_before_invoke = True
    tag = f"python-{random.randint(1000, 2000)}"
    build_overrides = {"Tag": tag}
    parameter_overrides = {"ImageUri": f"helloworldfunction:{tag}"}

    def setUp(self):
        self.url = "http://127.0.0.1:{}".format(self.port)

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=6000, method="thread")
    def test_changed_code_got_observed_and_loaded(self):
        response = requests.get(self.url + "/hello", timeout=300)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"hello": "world"})

        self._write_file_content(self.code_path, self.code_content_2)
        self.build()
        # wait till SAM got notified that the image got changed
        sleep(2)
        response = requests.get(self.url + "/hello", timeout=300)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"hello": "world2"})


class TestWatchingTemplateChangesLambdaFunctionHandlerChangedLazyContainer(WatchWarmContainersIntegBaseClass):
    template_content = """AWSTemplateFormatVersion : '2010-09-09'
Transform: AWS::Serverless-2016-10-31    
Resources:
  HelloWorldFunction:
    Type: AWS::Serverless::Function
    Properties:
      Handler: main.handler
      Runtime: python3.9
      CodeUri: .
      Timeout: 600
      Events:
        PathWithPathParams:
          Type: Api
          Properties:
            Method: GET
            Path: /hello
    """

    template_content_2 = """AWSTemplateFormatVersion : '2010-09-09'
Transform: AWS::Serverless-2016-10-31    
Resources:
  HelloWorldFunction:
    Type: AWS::Serverless::Function
    Properties:
      Handler: main.handler2
      Runtime: python3.9
      CodeUri: .
      Timeout: 600
      Events:
        PathWithPathParams:
          Type: Api
          Properties:
            Method: GET
            Path: /hello
    """
    code_content = """import json

def handler(event, context):
    return {"statusCode": 200, "body": json.dumps({"hello": "world"})}

def handler2(event, context):
    return {"statusCode": 200, "body": json.dumps({"hello": "world2"})}
    """

    docker_file_content = ""
    container_mode = ContainersInitializationMode.LAZY.value

    def setUp(self):
        self.url = "http://127.0.0.1:{}".format(self.port)

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_changed_code_got_observed_and_loaded(self):
        response = requests.get(self.url + "/hello", timeout=300)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"hello": "world"})

        self._write_file_content(self.template_path, self.template_content_2)
        # wait till SAM got notified that the source code got changed
        sleep(2)
        response = requests.get(self.url + "/hello", timeout=300)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"hello": "world2"})


class TestWatchingTemplateChangesLambdaFunctionCodeUriChangedLazyContainers(WatchWarmContainersIntegBaseClass):
    template_content = """AWSTemplateFormatVersion : '2010-09-09'
Transform: AWS::Serverless-2016-10-31    
Resources:
  HelloWorldFunction:
    Type: AWS::Serverless::Function
    Properties:
      Handler: main.handler
      Runtime: python3.7
      CodeUri: .
      Timeout: 600
      Events:
        PathWithPathParams:
          Type: Api
          Properties:
            Method: GET
            Path: /hello
    """

    template_content_2 = """AWSTemplateFormatVersion : '2010-09-09'
Transform: AWS::Serverless-2016-10-31    
Resources:
  HelloWorldFunction:
    Type: AWS::Serverless::Function
    Properties:
      Handler: main2.handler
      Runtime: python3.7
      CodeUri: dir
      Timeout: 600
      Events:
        PathWithPathParams:
          Type: Api
          Properties:
            Method: GET
            Path: /hello
    """
    code_content = """import json

def handler(event, context):
    return {"statusCode": 200, "body": json.dumps({"hello": "world"})}
    """
    code_content_2 = """import json

def handler(event, context):
    return {"statusCode": 200, "body": json.dumps({"hello": "world2"})}
        """

    docker_file_content = ""
    container_mode = ContainersInitializationMode.LAZY.value

    def setUp(self):
        self.url = "http://127.0.0.1:{}".format(self.port)

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_changed_code_got_observed_and_loaded(self):
        response = requests.get(self.url + "/hello", timeout=300)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"hello": "world"})

        self._write_file_content(self.template_path, self.template_content_2)
        self._write_file_content(self.code_path2, self.code_content_2)
        # wait till SAM got notified that the source code got changed
        sleep(2)
        response = requests.get(self.url + "/hello", timeout=300)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"hello": "world2"})


class TestWatchingTemplateChangesImageDockerFileChangedLocationLazyContainers(WatchWarmContainersIntegBaseClass):
    template_content = """AWSTemplateFormatVersion : '2010-09-09'
Transform: AWS::Serverless-2016-10-31    
Parameters:
  Tag:
    Type: String
  ImageUri:
    Type: String
Resources:
  HelloWorldFunction:
    Type: AWS::Serverless::Function
    Properties:
      PackageType: Image
      ImageConfig:
        Command:
          - main.handler
        Timeout: 600
      ImageUri: !Ref ImageUri
      Events:
        PathWithPathParams:
          Type: Api
          Properties:
            Method: GET
            Path: /hello
    Metadata:
      DockerTag: !Ref Tag
      DockerContext: .
      Dockerfile: Dockerfile
        """
    template_content_2 = """AWSTemplateFormatVersion : '2010-09-09'
Transform: AWS::Serverless-2016-10-31    
Parameters:
  Tag:
    Type: String
  ImageUri:
    Type: String
Resources:
  HelloWorldFunction:
    Type: AWS::Serverless::Function
    Properties:
      PackageType: Image
      ImageConfig:
        Command:
          - main.handler
        Timeout: 600
      ImageUri: !Ref ImageUri
      Events:
        PathWithPathParams:
          Type: Api
          Properties:
            Method: GET
            Path: /hello
    Metadata:
      DockerTag: !Ref Tag
      DockerContext: .
      Dockerfile: Dockerfile2
        """
    code_content = """import json

def handler(event, context):
    return {"statusCode": 200, "body": json.dumps({"hello": "world"})}"""
    code_content_2 = """import json

def handler(event, context):
    return {"statusCode": 200, "body": json.dumps({"hello": "world2"})}"""
    docker_file_content = """FROM public.ecr.aws/lambda/python:3.7
COPY main.py ./"""
    container_mode = ContainersInitializationMode.LAZY.value
    build_before_invoke = True
    tag = f"python-{random.randint(1000, 2000)}"
    build_overrides = {"Tag": tag}
    parameter_overrides = {"ImageUri": f"helloworldfunction:{tag}"}

    def setUp(self):
        self.url = "http://127.0.0.1:{}".format(self.port)

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=6000, method="thread")
    def test_changed_code_got_observed_and_loaded(self):
        response = requests.get(self.url + "/hello", timeout=300)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"hello": "world"})

        self._write_file_content(self.template_path, self.template_content_2)
        self._write_file_content(self.code_path, self.code_content_2)
        self._write_file_content(self.docker_file_path2, self.docker_file_content)
        self.build()
        # wait till SAM got notified that the image got changed
        sleep(2)
        response = requests.get(self.url + "/hello", timeout=300)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"hello": "world2"})


class TestApiPrecedenceInNestedStacks(StartApiIntegBaseClass):
    """
    Here we test when two APIs share the same path+method,
    whoever located in top level stack should win.
    See SamApiProvider::merge_routes() docstring for the full detail.
    """

    template_path = "/testdata/start_api/nested-templates/template-precedence-root.yaml"

    def setUp(self):
        self.url = "http://127.0.0.1:{}".format(self.port)

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_should_call_function_in_root_stack_if_path_method_collide(self):
        response = requests.post(self.url + "/path1", timeout=300)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"hello": "world"})

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_should_call_function_in_child_stack_if_only_path_collides(self):
        response = requests.get(self.url + "/path1", timeout=300)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode("utf-8"), "42")

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_should_call_function_in_child_stack_if_nothing_collides(self):
        data = "I don't collide with any other APIs"
        response = requests.post(self.url + "/path2", data=data, timeout=300)

        self.assertEqual(response.status_code, 200)
        response_data = response.json()
        self.assertEqual(response_data.get("body"), data)

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_should_not_call_non_existent_path(self):
        data = "some data"
        response = requests.post(self.url + "/path404", data=data, timeout=300)

        self.assertEqual(response.status_code, 403)

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_should_not_call_non_mounting_method(self):
        data = "some data"
        response = requests.put(self.url + "/path2", data=data, timeout=300)

        self.assertEqual(response.status_code, 403)


@parameterized_class(
    ("template_path",),
    [
        ("/testdata/start_api/template.yaml",),
        ("/testdata/start_api/nested-templates/template-parent.yaml",),
    ],
)
class TestServiceWithCustomInvokeImages(StartApiIntegBaseClass):
    """
    Testing general requirements around the Service that powers `sam local start-api` using invoke images
    """

    invoke_image = [
        "amazon/aws-sam-cli-emulation-image-python3.9",
        "HelloWorldFunction=public.ecr.aws/sam/emulation-python3.9",
    ]

    def setUp(self):
        self.url = "http://127.0.0.1:{}".format(self.port)

    def test_static_directory(self):
        pass

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_calling_proxy_endpoint_custom_invoke_image(self):
        response = requests.get(self.url + "/proxypath/this/is/some/path", timeout=300)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"hello": "world"})

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_get_call_with_path_setup_with_any_implicit_api_custom_invoke_image(self):
        """
        Get Request to a path that was defined as ANY in SAM through AWS::Serverless::Function Events
        """
        response = requests.get(self.url + "/anyandall", timeout=300)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"hello": "world"})

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_post_call_with_path_setup_with_any_implicit_api_custom_invoke_image(self):
        """
        Post Request to a path that was defined as ANY in SAM through AWS::Serverless::Function Events
        """
        response = requests.post(self.url + "/anyandall", json={}, timeout=300)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"hello": "world"})

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_put_call_with_path_setup_with_any_implicit_api_custom_invoke_image(self):
        """
        Put Request to a path that was defined as ANY in SAM through AWS::Serverless::Function Events
        """
        response = requests.put(self.url + "/anyandall", json={}, timeout=300)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"hello": "world"})


class WarmContainersWithRemoteLayersBase(TestWarmContainersBaseClass):
    layer_utils = LayerUtils()
    layer_cache_base_dir = str(Path().home().joinpath("integ_layer_cache"))
    parameter_overrides: Dict[str, str] = {}

    @classmethod
    def setUpClass(cls) -> None:
        cls.layer_utils.upsert_layer(LayerUtils.generate_layer_name(), "LayerArn", "layer1.zip")
        for key, val in cls.layer_utils.parameters_overrides.items():
            cls.parameter_overrides[key] = val
        super().setUpClass()

    @classmethod
    def tearDownClass(self) -> None:
        self.layer_utils.delete_layers()
        integ_layer_cache_dir = Path().home().joinpath("integ_layer_cache")
        if integ_layer_cache_dir.exists():
            shutil.rmtree(str(integ_layer_cache_dir))
        super().tearDownClass()


class TestWarmContainersRemoteLayers(WarmContainersWithRemoteLayersBase):
    template_path = "/testdata/start_api/template-warm-containers-layers.yaml"
    container_mode = ContainersInitializationMode.EAGER.value
    mode_env_variable = str(uuid.uuid4())
    parameter_overrides = {"ModeEnvVariable": mode_env_variable}

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_all_containers_are_initialized_before_any_invoke(self):
        initiated_containers = self.count_running_containers()
        # Ensure only one function has spun up, remote layer shouldn't create another container
        self.assertEqual(initiated_containers, 1)

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_can_invoke_lambda_layer_successfully(self):
        response = requests.get(self.url + "/", timeout=300)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode("utf-8"), '"Layer1"')


class TestWarmContainersRemoteLayersLazyInvoke(WarmContainersWithRemoteLayersBase):
    template_path = "/testdata/start_api/template-warm-containers-layers.yaml"
    container_mode = ContainersInitializationMode.LAZY.value
    mode_env_variable = str(uuid.uuid4())
    parameter_overrides = {"ModeEnvVariable": mode_env_variable}

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_can_invoke_lambda_layer_successfully(self):
        response = requests.get(self.url + "/", timeout=300)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode("utf-8"), '"Layer1"')
