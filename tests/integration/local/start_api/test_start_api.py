import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from time import time

from .start_api_integ_base import StartApiIntegBaseClass


class TestParallelRequests(StartApiIntegBaseClass):
    """
    Test Class centered around sending parallel requests to the service `sam local start-api`
    """
    # This is here so the setUpClass doesn't fail. Set to this something else once the class is implemented
    template_path = "/testdata/start_api/template.yaml"

    def setUp(self):
        self.url = "http://127.0.0.1:{}".format(self.port)

    def test_same_endpoint(self):
        """
        Send two requests to the same path at the same time. This is to ensure we can handle
        multiple requests at once and do not block/queue up requests
        """
        number_of_requests = 10
        start_time = time()
        thread_pool = ThreadPoolExecutor(number_of_requests)

        futures = [thread_pool.submit(requests.get, self.url + "/sleepfortenseconds/function1")
                   for _ in range(0, number_of_requests)]
        results = [r.result() for r in as_completed(futures)]

        end_time = time()

        self.assertEquals(len(results), 10)
        self.assertGreater(end_time - start_time, 10)
        self.assertLess(end_time - start_time, 20)

        for result in results:
            self.assertEquals(result.status_code, 200)
            self.assertEquals(result.json(), {"message": "HelloWorld! I just slept and waking up."})

    def test_different_endpoints(self):
        """
        Send two requests to different paths at the same time. This is to ensure we can handle
        multiple requests for different paths and do not block/queue up the requests
        """
        number_of_requests = 10
        start_time = time()
        thread_pool = ThreadPoolExecutor(10)

        test_url_paths = ["/sleepfortenseconds/function0", "/sleepfortenseconds/function1"]

        futures = [thread_pool.submit(requests.get, self.url + test_url_paths[function_num % len(test_url_paths)])
                   for function_num in range(0, number_of_requests)]
        results = [r.result() for r in as_completed(futures)]

        end_time = time()

        self.assertEquals(len(results), 10)
        self.assertGreater(end_time - start_time, 10)
        self.assertLess(end_time - start_time, 20)

        for result in results:
            self.assertEquals(result.status_code, 200)
            self.assertEquals(result.json(), {"message": "HelloWorld! I just slept and waking up."})


class TestServiceErrorResponses(StartApiIntegBaseClass):
    """
    Test Class centered around the Error Responses the Service can return for a given api
    """
    # This is here so the setUpClass doesn't fail. Set to this something else once the class is implemented.
    template_path = "/testdata/start_api/template.yaml"

    def setUp(self):
        self.url = "http://127.0.0.1:{}".format(self.port)

    def test_invalid_http_verb_for_endpoint(self):
        response = requests.get(self.url + "/id")

        self.assertEquals(response.status_code, 403)
        self.assertEquals(response.json(), {"message": "Missing Authentication Token"})

    def test_invalid_response_from_lambda(self):
        response = requests.get(self.url + "/invalidresponsereturned")

        self.assertEquals(response.status_code, 502)
        self.assertEquals(response.json(), {"message": "Internal server error"})

    def test_request_timeout(self):
        pass


class TestService(StartApiIntegBaseClass):
    """
    Testing general requirements around the Service that powers `sam local start-api`
    """
    template_path = "/testdata/start_api/template.yaml"

    def setUp(self):
        self.url = "http://127.0.0.1:{}".format(self.port)

    def test_static_directory(self):
        pass

    def test_calling_proxy_endpoint(self):
        response = requests.get(self.url + "/proxypath/this/is/some/path")

        self.assertEquals(response.status_code, 200)
        self.assertEquals(response.json(), {'hello': 'world'})

    def test_get_call_with_path_setup_with_any_implicit_api(self):
        """
        Get Request to a path that was defined as ANY in SAM through AWS::Serverless::Function Events
        """
        response = requests.get(self.url + "/anyandall")

        self.assertEquals(response.status_code, 200)
        self.assertEquals(response.json(), {'hello': 'world'})

    def test_post_call_with_path_setup_with_any_implicit_api(self):
        """
        Post Request to a path that was defined as ANY in SAM through AWS::Serverless::Function Events
        """
        response = requests.post(self.url + "/anyandall", json={})

        self.assertEquals(response.status_code, 200)
        self.assertEquals(response.json(), {'hello': 'world'})

    def test_put_call_with_path_setup_with_any_implicit_api(self):
        """
        Put Request to a path that was defined as ANY in SAM through AWS::Serverless::Function Events
        """
        response = requests.put(self.url + "/anyandall", json={})

        self.assertEquals(response.status_code, 200)
        self.assertEquals(response.json(), {'hello': 'world'})

    def test_head_call_with_path_setup_with_any_implicit_api(self):
        """
        Head Request to a path that was defined as ANY in SAM through AWS::Serverless::Function Events
        """
        response = requests.head(self.url + "/anyandall")

        self.assertEquals(response.status_code, 200)

    def test_delete_call_with_path_setup_with_any_implicit_api(self):
        """
        Delete Request to a path that was defined as ANY in SAM through AWS::Serverless::Function Events
        """
        response = requests.delete(self.url + "/anyandall")

        self.assertEquals(response.status_code, 200)
        self.assertEquals(response.json(), {'hello': 'world'})

    def test_options_call_with_path_setup_with_any_implicit_api(self):
        """
        Options Request to a path that was defined as ANY in SAM through AWS::Serverless::Function Events
        """
        response = requests.options(self.url + "/anyandall")

        self.assertEquals(response.status_code, 200)

    def test_patch_call_with_path_setup_with_any_implicit_api(self):
        """
        Patch Request to a path that was defined as ANY in SAM through AWS::Serverless::Function Events
        """
        response = requests.patch(self.url + "/anyandall")

        self.assertEquals(response.status_code, 200)
        self.assertEquals(response.json(), {'hello': 'world'})


class TestStartApiWithSwaggerApis(StartApiIntegBaseClass):
    template_path = "/testdata/start_api/swagger-template.yaml"
    binary_data_file = "testdata/start_api/binarydata.gif"

    def setUp(self):
        self.url = "http://127.0.0.1:{}".format(self.port)

    def test_get_call_with_path_setup_with_any_swagger(self):
        """
        Get Request to a path that was defined as ANY in SAM through Swagger
        """
        response = requests.get(self.url + "/anyandall")

        self.assertEquals(response.status_code, 200)
        self.assertEquals(response.json(), {'hello': 'world'})

    def test_post_call_with_path_setup_with_any_swagger(self):
        """
        Post Request to a path that was defined as ANY in SAM through Swagger
        """
        response = requests.post(self.url + "/anyandall", json={})

        self.assertEquals(response.status_code, 200)
        self.assertEquals(response.json(), {'hello': 'world'})

    def test_put_call_with_path_setup_with_any_swagger(self):
        """
        Put Request to a path that was defined as ANY in SAM through Swagger
        """
        response = requests.put(self.url + "/anyandall", json={})

        self.assertEquals(response.status_code, 200)
        self.assertEquals(response.json(), {'hello': 'world'})

    def test_head_call_with_path_setup_with_any_swagger(self):
        """
        Head Request to a path that was defined as ANY in SAM through Swagger
        """
        response = requests.head(self.url + "/anyandall")

        self.assertEquals(response.status_code, 200)

    def test_delete_call_with_path_setup_with_any_swagger(self):
        """
        Delete Request to a path that was defined as ANY in SAM through Swagger
        """
        response = requests.delete(self.url + "/anyandall")

        self.assertEquals(response.status_code, 200)
        self.assertEquals(response.json(), {'hello': 'world'})

    def test_options_call_with_path_setup_with_any_swagger(self):
        """
        Options Request to a path that was defined as ANY in SAM through Swagger
        """
        response = requests.options(self.url + "/anyandall")

        self.assertEquals(response.status_code, 200)

    def test_patch_call_with_path_setup_with_any_swagger(self):
        """
        Patch Request to a path that was defined as ANY in SAM through Swagger
        """
        response = requests.patch(self.url + "/anyandall")

        self.assertEquals(response.status_code, 200)
        self.assertEquals(response.json(), {'hello': 'world'})

    def test_function_not_defined_in_template(self):
        response = requests.get(self.url + "/nofunctionfound")

        self.assertEquals(response.status_code, 502)
        self.assertEquals(response.json(), {"message": "No function defined for resource method"})

    def test_function_with_no_api_event_is_reachable(self):
        response = requests.get(self.url + "/functionwithnoapievent")

        self.assertEquals(response.status_code, 200)
        self.assertEquals(response.json(), {'hello': 'world'})

    def test_lambda_function_resource_is_reachable(self):
        response = requests.get(self.url + "/nonserverlessfunction")

        self.assertEquals(response.status_code, 200)
        self.assertEquals(response.json(), {'hello': 'world'})

    def test_binary_request(self):
        """
        This tests that the service can accept and invoke a lambda when given binary data in a request
        """
        input_data = self.get_binary_data(self.binary_data_file)
        response = requests.post(self.url + '/echobase64eventbody',
                                 headers={"Content-Type": "image/gif"},
                                 data=input_data)

        self.assertEquals(response.status_code, 200)
        self.assertEquals(response.headers.get("Content-Type"), "image/gif")
        self.assertEquals(response.content, input_data)

    def test_binary_response(self):
        """
        Binary data is returned correctly
        """
        expected = self.get_binary_data(self.binary_data_file)

        response = requests.get(self.url + '/base64response')

        self.assertEquals(response.status_code, 200)
        self.assertEquals(response.headers.get("Content-Type"), "image/gif")
        self.assertEquals(response.content, expected)


class TestServiceResponses(StartApiIntegBaseClass):
    """
    Test Class centered around the different responses that can happen in Lambda and pass through start-api
    """
    template_path = "/testdata/start_api/template.yaml"
    binary_data_file = "testdata/start_api/binarydata.gif"

    def setUp(self):
        self.url = "http://127.0.0.1:{}".format(self.port)

    def test_binary_response(self):
        """
        Binary data is returned correctly
        """
        expected = self.get_binary_data(self.binary_data_file)

        response = requests.get(self.url + '/base64response')

        self.assertEquals(response.status_code, 200)
        self.assertEquals(response.headers.get("Content-Type"), "image/gif")
        self.assertEquals(response.content, expected)

    def test_default_header_content_type(self):
        """
        Test that if no ContentType is given the default is "application/json"
        """
        response = requests.get(self.url + "/onlysetstatuscode")

        self.assertEquals(response.status_code, 200)
        self.assertEquals(response.content.decode('utf-8'), "no data")
        self.assertEquals(response.headers.get("Content-Type"), "application/json")

    def test_default_status_code(self):
        """
        Test that if no status_code is given, the status code is 200
        :return:
        """
        response = requests.get(self.url + "/onlysetbody")

        self.assertEquals(response.status_code, 200)
        self.assertEquals(response.json(), {'hello': 'world'})

    def test_default_body(self):
        """
        Test that if no body is given, the response is 'no data'
        """
        response = requests.get(self.url + "/onlysetstatuscode")

        self.assertEquals(response.status_code, 200)
        self.assertEquals(response.content.decode('utf-8'), "no data")

    def test_function_writing_to_stdout(self):
        response = requests.get(self.url + "/writetostdout")

        self.assertEquals(response.status_code, 200)
        self.assertEquals(response.json(), {'hello': 'world'})

    def test_function_writing_to_stderr(self):
        response = requests.get(self.url + "/writetostderr")

        self.assertEquals(response.status_code, 200)
        self.assertEquals(response.json(), {'hello': 'world'})


class TestServiceRequests(StartApiIntegBaseClass):
    """
    Test Class centered around the different requests that can happen
    """
    template_path = "/testdata/start_api/template.yaml"
    binary_data_file = "testdata/start_api/binarydata.gif"

    def setUp(self):
        self.url = "http://127.0.0.1:{}".format(self.port)

    def test_binary_request(self):
        """
        This tests that the service can accept and invoke a lambda when given binary data in a request
        """
        input_data = self.get_binary_data(self.binary_data_file)
        response = requests.post(self.url + '/echobase64eventbody',
                                 headers={"Content-Type": "image/gif"},
                                 data=input_data)

        self.assertEquals(response.status_code, 200)
        self.assertEquals(response.headers.get("Content-Type"), "image/gif")
        self.assertEquals(response.content, input_data)

    def test_request_with_form_data(self):
        """
        Form-encoded data should be put into the Event to Lambda
        """
        response = requests.post(self.url + "/echoeventbody",
                                 headers={"Content-Type": "application/x-www-form-urlencoded"},
                                 data='key=value')

        self.assertEquals(response.status_code, 200)

        response_data = response.json()

        self.assertEquals(response_data.get("headers").get("Content-Type"), "application/x-www-form-urlencoded")
        self.assertEquals(response_data.get("body"), "key=value")

    def test_request_to_an_endpoint_with_two_different_handlers(self):
        response = requests.get(self.url + "/echoeventbody")

        self.assertEquals(response.status_code, 200)

        response_data = response.json()

        self.assertEquals(response_data.get("handler"), 'echo_event_handler_2')

    def test_request_with_query_params(self):
        """
        Query params given should be put into the Event to Lambda
        """
        response = requests.get(self.url + "/id/4",
                                params={"key": "value"})

        self.assertEquals(response.status_code, 200)

        response_data = response.json()

        self.assertEquals(response_data.get("queryStringParameters"), {"key": "value"})

    def test_request_with_list_of_query_params(self):
        """
        Query params given should be put into the Event to Lambda
        """
        response = requests.get(self.url + "/id/4",
                                params={"key": ["value", "value2"]})

        self.assertEquals(response.status_code, 200)

        response_data = response.json()

        self.assertEquals(response_data.get("queryStringParameters"), {"key": "value2"})

    def test_request_with_path_params(self):
        """
        Path Parameters given should be put into the Event to Lambda
        """
        response = requests.get(self.url + "/id/4")

        self.assertEquals(response.status_code, 200)

        response_data = response.json()

        self.assertEquals(response_data.get("pathParameters"), {"id": "4"})

    def test_request_with_many_path_params(self):
        """
        Path Parameters given should be put into the Event to Lambda
        """
        response = requests.get(self.url + "/id/4/user/jacob")

        self.assertEquals(response.status_code, 200)

        response_data = response.json()

        self.assertEquals(response_data.get("pathParameters"), {"id": "4", "user": "jacob"})

    def test_forward_headers_are_added_to_event(self):
        """
        Test the Forwarding Headers exist in the Api Event to Lambda
        """
        response = requests.get(self.url + "/id/4")

        response_data = response.json()

        self.assertEquals(response_data.get("headers").get("X-Forwarded-Proto"), "http")
        self.assertEquals(response_data.get("headers").get("X-Forwarded-Port"), self.port)
