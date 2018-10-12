from concurrent.futures import ThreadPoolExecutor, as_completed
from time import time

import boto3
from botocore import UNSIGNED
from botocore.config import Config
from botocore.exceptions import ClientError

from .start_lambda_api_integ_base import StartLambdaIntegBaseClass


class TestParallelRequests(StartLambdaIntegBaseClass):
    template_path = "/testdata/invoke/template.yml"

    def setUp(self):
        self.url = "http://127.0.0.1:{}".format(self.port)
        self.lambda_client = boto3.client('lambda',
                                          endpoint_url=self.url,
                                          use_ssl=False,
                                          verify=False,
                                          config=Config(signature_version=UNSIGNED,
                                                        read_timeout=120,
                                                        retries={'max_attempts': 0}))

    def test_same_endpoint(self):
        """
        Send two requests to the same path at the same time. This is to ensure we can handle
        multiple requests at once and do not block/queue up requests
        """
        number_of_requests = 10
        start_time = time()
        thread_pool = ThreadPoolExecutor(number_of_requests)

        futures = [thread_pool.submit(self.lambda_client.invoke, FunctionName="HelloWorldSleepFunction")
                   for _ in range(0, number_of_requests)]
        results = [r.result() for r in as_completed(futures)]

        end_time = time()

        self.assertEquals(len(results), 10)
        self.assertGreater(end_time - start_time, 10)
        self.assertLess(end_time - start_time, 20)

        for result in results:
            self.assertEquals(result.get("Payload").read().decode('utf-8'), '"Slept for 10s"')


class TestLambdaToLambdaInvoke(StartLambdaIntegBaseClass):
    template_path = "/testdata/start_lambda/template.yml"

    def setUp(self):
        self.url = "http://127.0.0.1:{}".format(self.port)
        self.lambda_client = boto3.client('lambda',
                                          endpoint_url=self.url,
                                          use_ssl=False,
                                          verify=False,
                                          config=Config(signature_version=UNSIGNED,
                                                        read_timeout=120,
                                                        retries={'max_attempts': 0}))

    def test_local_lambda_calling_local_lambda(self):
        pass


class TestLambdaServiceErrorCases(StartLambdaIntegBaseClass):
    template_path = "/testdata/invoke/template.yml"

    def setUp(self):
        self.url = "http://127.0.0.1:{}".format(self.port)
        self.lambda_client = boto3.client('lambda',
                                          endpoint_url=self.url,
                                          use_ssl=False,
                                          verify=False,
                                          config=Config(signature_version=UNSIGNED,
                                                        read_timeout=120,
                                                        retries={'max_attempts': 0}))

    def test_invoke_with_non_json_data(self):
        expected_error_message = "An error occurred (InvalidRequestContent) when calling the Invoke operation: " \
                                 "Could not parse request body into json: No JSON object could be decoded"

        with self.assertRaises(ClientError) as error:
            self.lambda_client.invoke(FunctionName="EchoEventFunction", Payload='notat:asdfasdf')

        self.assertEquals(str(error.exception), expected_error_message)

    def test_invoke_with_log_type_not_None(self):
        expected_error_message = "An error occurred (NotImplemented) when calling the Invoke operation: " \
                                 "log-type: Tail is not supported. None is only supported."

        with self.assertRaises(ClientError) as error:
            self.lambda_client.invoke(FunctionName="EchoEventFunction", LogType="Tail")

        self.assertEquals(str(error.exception), expected_error_message)

    def test_invoke_with_invocation_type_not_RequestResponse(self):
        expected_error_message = "An error occurred (NotImplemented) when calling the Invoke operation: " \
                                 "invocation-type: DryRun is not supported. RequestResponse is only supported."

        with self.assertRaises(ClientError) as error:
            self.lambda_client.invoke(FunctionName="EchoEventFunction", InvocationType="DryRun")

        self.assertEquals(str(error.exception), expected_error_message)


class TestLambdaService(StartLambdaIntegBaseClass):
    template_path = "/testdata/invoke/template.yml"

    def setUp(self):
        self.url = "http://127.0.0.1:{}".format(self.port)
        self.lambda_client = boto3.client('lambda',
                                          endpoint_url=self.url,
                                          use_ssl=False,
                                          verify=False,
                                          config=Config(signature_version=UNSIGNED,
                                                        read_timeout=120,
                                                        retries={'max_attempts': 0}))

    def test_invoke_with_data(self):
        response = self.lambda_client.invoke(FunctionName="EchoEventFunction", Payload='"This is json data"')

        self.assertEquals(response.get("Payload").read().decode('utf-8'), '"This is json data"')
        self.assertIsNone(response.get("FunctionError"))
        self.assertEquals(response.get("StatusCode"), 200)

    def test_invoke_with_no_data(self):
        response = self.lambda_client.invoke(FunctionName="EchoEventFunction")

        self.assertEquals(response.get("Payload").read().decode('utf-8'), '{}')
        self.assertIsNone(response.get("FunctionError"))
        self.assertEquals(response.get("StatusCode"), 200)

    def test_invoke_with_log_type_None(self):
        response = self.lambda_client.invoke(FunctionName="EchoEventFunction", LogType='None')

        self.assertEquals(response.get("Payload").read().decode('utf-8'), '{}')
        self.assertIsNone(response.get("FunctionError"))
        self.assertEquals(response.get("StatusCode"), 200)

    def test_invoke_with_invocation_type_RequestResponse(self):
        response = self.lambda_client.invoke(FunctionName="EchoEventFunction", InvocationType='RequestResponse')

        self.assertEquals(response.get("Payload").read().decode('utf-8'), '{}')
        self.assertIsNone(response.get("FunctionError"))
        self.assertEquals(response.get("StatusCode"), 200)

    def test_lambda_function_raised_error(self):
        response = self.lambda_client.invoke(FunctionName="RaiseExceptionFunction", InvocationType='RequestResponse')

        self.assertEquals(response.get("Payload").read().decode('utf-8'),
                          '{"errorMessage": "Lambda is raising an exception", '
                          '"errorType": "Exception", '
                          '"stackTrace": [["/var/task/main.py", 47, "raise_exception", '
                          '"raise Exception(\\"Lambda is raising an exception\\")"]]}')
        self.assertEquals(response.get("FunctionError"), 'Unhandled')
        self.assertEquals(response.get("StatusCode"), 200)

    def test_invoke_with_function_timeout(self):
        """
        This behavior does not match the actually Lambda Service. For functions that timeout, data returned like the
        following:
        {"errorMessage":"<timestamp> <request_id> Task timed out after 5.00 seconds"}

        For Local Lambda's, however, timeouts are an interrupt on the thread that runs invokes the function. Since the
        invoke is on a different thread, we do not (currently) have a way to communicate this back to the caller. So
        when a timeout happens locally, we do not add the FunctionError: Unhandled to the response and have an empty
        string as the data returned (because no data was found in stdout from the container).
        """
        response = self.lambda_client.invoke(FunctionName="TimeoutFunction")

        self.assertEquals(response.get("Payload").read().decode('utf-8'), '')
        self.assertIsNone(response.get("FunctionError"))
        self.assertEquals(response.get("StatusCode"), 200)
