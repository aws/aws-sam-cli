import base64
from concurrent.futures import ThreadPoolExecutor, as_completed
from time import time

import pytest
import requests

from tests.integration.local.start_api.start_api_integ_base import CDKStartApiIntegPythonBase


class TestService(CDKStartApiIntegPythonBase):
    """
    Testing general requirements around the Service that powers `sam local start-api`
    """

    template_path = "testdata/start_api/cdk/python/aws-lambda-function"

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

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_get_call_with_path_setup_with_any_implicit_api(self):
        """
        Get Request to a path that was defined as ANY in SAM through AWS::Serverless::Function Events
        """
        response = requests.get(self.url + "/anyandall", timeout=300)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"hello": "world"})

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_post_call_with_path_setup_with_any_implicit_api(self):
        """
        Post Request to a path that was defined as ANY in SAM through AWS::Serverless::Function Events
        """
        response = requests.post(self.url + "/anyandall", json={}, timeout=300)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"hello": "world"})

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_put_call_with_path_setup_with_any_implicit_api(self):
        """
        Put Request to a path that was defined as ANY in SAM through AWS::Serverless::Function Events
        """
        response = requests.put(self.url + "/anyandall", json={}, timeout=300)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"hello": "world"})

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_head_call_with_path_setup_with_any_implicit_api(self):
        """
        Head Request to a path that was defined as ANY in SAM through AWS::Serverless::Function Events
        """
        response = requests.head(self.url + "/anyandall", timeout=300)

        self.assertEqual(response.status_code, 200)

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_delete_call_with_path_setup_with_any_implicit_api(self):
        """
        Delete Request to a path that was defined as ANY in SAM through AWS::Serverless::Function Events
        """
        response = requests.delete(self.url + "/anyandall", timeout=300)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"hello": "world"})

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_options_call_with_path_setup_with_any_implicit_api(self):
        """
        Options Request to a path that was defined as ANY in SAM through AWS::Serverless::Function Events
        """
        response = requests.options(self.url + "/anyandall", timeout=300)

        self.assertEqual(response.status_code, 200)

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_patch_call_with_path_setup_with_any_implicit_api(self):
        """
        Patch Request to a path that was defined as ANY in SAM through AWS::Serverless::Function Events
        """
        response = requests.patch(self.url + "/anyandall", timeout=300)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"hello": "world"})

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


class TestParallelRequests(CDKStartApiIntegPythonBase):
    """
    Test Class centered around sending parallel requests to the service `sam local start-api`
    """

    template_path = "testdata/start_api/cdk/python/aws-lambda-function"

    def setUp(self):
        self.url = "http://127.0.0.1:{}".format(self.port)

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


class TestServiceErrorResponses(CDKStartApiIntegPythonBase):
    """
    Test Class centered around the Error Responses the Service can return for a given api
    """

    # This is here so the setUpClass doesn't fail. Set to this something else once the class is implemented.
    template_path = "testdata/start_api/cdk/python/aws-lambda-function"

    def setUp(self):
        self.url = "http://127.0.0.1:{}".format(self.port)

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_invalid_http_verb_for_endpoint(self):
        response = requests.get(self.url + "/id", timeout=300)

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json(), {"message": "Missing Authentication Token"})

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_invalid_response_from_lambda(self):
        response = requests.get(self.url + "/invalidresponsereturned", timeout=300)

        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.json(), {"message": "Internal server error"})

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_invalid_json_response_from_lambda(self):
        response = requests.get(self.url + "/invalidresponsehash", timeout=300)

        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.json(), {"message": "Internal server error"})

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_request_timeout(self):
        pass


class TestServiceResponses(CDKStartApiIntegPythonBase):
    """
    Test Class centered around the different responses that can happen in Lambda and pass through start-api
    """

    template_path = "testdata/start_api/cdk/python/aws-lambda-function"

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


class TestServiceRequests(CDKStartApiIntegPythonBase):
    """
    Test Class centered around the different requests that can happen
    """

    template_path = "testdata/start_api/cdk/python/aws-lambda-function"

    def setUp(self):
        self.url = "http://127.0.0.1:{}".format(self.port)

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


class TestStartApiWithStage(CDKStartApiIntegPythonBase):
    """
    Test Class centered around the different responses that can happen in Lambda and pass through start-api
    """

    template_path = "testdata/start_api/cdk/python/aws-lambda-function/"

    def setUp(self):
        self.url = "http://127.0.0.1:{}".format(self.port)

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_default_stage_name(self):
        response = requests.get(self.url + "/echoeventbody", timeout=300)

        self.assertEqual(response.status_code, 200)

        response_data = response.json()

        self.assertEqual(response_data.get("requestContext", {}).get("stage"), "prod")


class TestStartApiWithSwaggerApis(CDKStartApiIntegPythonBase):
    template_path = "testdata/start_api/cdk/python/aws-api-resource"
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
    def test_decoded_binary_response_base64encoded_field_is_priority(self):
        """
        Binary data is returned correctly
        """
        expected = base64.b64encode(self.get_binary_data(self.binary_data_file))

        response = requests.get(self.url + "/decodedbase64responsebas64encodedpriority", timeout=300)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get("Content-Type"), "image/gif")
        self.assertEqual(response.content, expected)


# TODO: Figure out why OPTIONS requests throw an error in sam-cli
# class TestServiceCorsSwaggerRequests(CDKStartApiIntegPythonBase):
#     """
#     Test to check that the correct headers are being added with Cors with swagger code
#     """
#
#     template_path = "testdata/start_api/cdk/python/aws-api-resource"
#     binary_data_file = "testdata/start_api/binarydata.gif"
#
#     def setUp(self):
#         self.url = "http://127.0.0.1:{}".format(self.port)
#
#     @pytest.mark.flaky(reruns=3)
#     @pytest.mark.timeout(timeout=600, method="thread")
#     def test_cors_swagger_options(self):
#         """
#         This tests that the Cors are added to option requests in the swagger template
#         """
#         response = requests.options(self.url + "/echobase64eventbody", timeout=300)
#
#         self.assertEqual(response.status_code, 200)
#
#         self.assertEqual(response.headers.get("Access-Control-Allow-Origin"), "*")
#         self.assertEqual(response.headers.get("Access-Control-Allow-Headers"), "origin, x-requested-with")
#         self.assertEqual(response.headers.get("Access-Control-Allow-Methods"), "GET,OPTIONS")
#         self.assertEqual(response.headers.get("Access-Control-Allow-Credentials"), "true")
#         self.assertEqual(response.headers.get("Access-Control-Max-Age"), "510")
