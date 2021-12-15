import boto3
import pytest
from botocore import UNSIGNED
from botocore.config import Config
from botocore.exceptions import ClientError

from tests.integration.local.start_lambda.start_lambda_api_integ_base import StartLambdaIntegBaseClass


class TestCDKLambdaService(StartLambdaIntegBaseClass):
    template_path = "/testdata/invoke/cdk/cdk_template.yaml"

    def setUp(self):
        self.url = "http://127.0.0.1:{}".format(self.port)
        self.lambda_client = boto3.client(
            "lambda",
            endpoint_url=self.url,
            region_name="us-east-1",
            use_ssl=False,
            verify=False,
            config=Config(signature_version=UNSIGNED, read_timeout=120, retries={"max_attempts": 0}),
        )

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=300, method="thread")
    def test_invoke_with_no_data(self):
        response = self.lambda_client.invoke(FunctionName="HelloWorldFunction")

        self.assertEqual(response.get("Payload").read().decode("utf-8"), '"Hello world!"')
        self.assertIsNone(response.get("FunctionError"))
        self.assertEqual(response.get("StatusCode"), 200)

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=300, method="thread")
    def test_invoke_with_data(self):
        response = self.lambda_client.invoke(FunctionName="CDKEchoEventFunction", Payload='"This is json data"')

        self.assertEqual(response.get("Payload").read().decode("utf-8"), '"This is json data"')
        self.assertIsNone(response.get("FunctionError"))
        self.assertEqual(response.get("StatusCode"), 200)

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=300, method="thread")
    def test_invoke_with_no_data_empty_response(self):
        response = self.lambda_client.invoke(FunctionName="CDKEchoEventFunction")

        self.assertEqual(response.get("Payload").read().decode("utf-8"), "{}")
        self.assertIsNone(response.get("FunctionError"))
        self.assertEqual(response.get("StatusCode"), 200)

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=300, method="thread")
    def test_invoke_with_log_type_None(self):
        response = self.lambda_client.invoke(FunctionName="CDKEchoEventFunction", LogType="None")

        self.assertEqual(response.get("Payload").read().decode("utf-8"), "{}")
        self.assertIsNone(response.get("FunctionError"))
        self.assertEqual(response.get("StatusCode"), 200)

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=300, method="thread")
    def test_invoke_with_invocation_type_RequestResponse(self):
        response = self.lambda_client.invoke(FunctionName="CDKEchoEventFunction", InvocationType="RequestResponse")

        self.assertEqual(response.get("Payload").read().decode("utf-8"), "{}")
        self.assertIsNone(response.get("FunctionError"))
        self.assertEqual(response.get("StatusCode"), 200)


class TestLambdaServiceErrorCases(StartLambdaIntegBaseClass):
    template_path = "/testdata/invoke/cdk/cdk_template.yaml"

    def setUp(self):
        self.url = "http://127.0.0.1:{}".format(self.port)
        self.lambda_client = boto3.client(
            "lambda",
            endpoint_url=self.url,
            region_name="us-east-1",
            use_ssl=False,
            verify=False,
            config=Config(signature_version=UNSIGNED, read_timeout=120, retries={"max_attempts": 0}),
        )

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=300, method="thread")
    def test_invoke_with_non_json_data(self):
        expected_error_message = (
            "An error occurred (InvalidRequestContent) when calling the Invoke operation: "
            "Could not parse request body into json: No JSON object could be decoded"
        )

        with self.assertRaises(ClientError) as error:
            self.lambda_client.invoke(FunctionName="EchoEventFunction", Payload="notat:asdfasdf")

        self.assertEqual(str(error.exception), expected_error_message)

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=300, method="thread")
    def test_invoke_with_log_type_not_None(self):
        expected_error_message = (
            "An error occurred (NotImplemented) when calling the Invoke operation: "
            "log-type: Tail is not supported. None is only supported."
        )

        with self.assertRaises(ClientError) as error:
            self.lambda_client.invoke(FunctionName="EchoEventFunction", LogType="Tail")

        self.assertEqual(str(error.exception), expected_error_message)

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=300, method="thread")
    def test_invoke_with_invocation_type_not_RequestResponse(self):
        expected_error_message = (
            "An error occurred (NotImplemented) when calling the Invoke operation: "
            "invocation-type: DryRun is not supported. RequestResponse is only supported."
        )

        with self.assertRaises(ClientError) as error:
            self.lambda_client.invoke(FunctionName="EchoEventFunction", InvocationType="DryRun")

        self.assertEqual(str(error.exception), expected_error_message)
