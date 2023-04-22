import pytest
import requests
from tests.integration.local.start_api.start_api_integ_base import (
    StartApiIntegBaseClass,
    WritableStartApiIntegBaseClass,
)
from parameterized import parameterized_class


@parameterized_class(
    ("parameter_overrides", "template_path"),
    [
        ({"AuthOverride": "RequestAuthorizerV2"}, "/testdata/start_api/lambda_authorizers/serverless-http-props.yaml"),
        (
            {"AuthOverride": "RequestAuthorizerV2Simple"},
            "/testdata/start_api/lambda_authorizers/serverless-http-props.yaml",
        ),
        ({"AuthOverride": "RequestAuthorizerV1"}, "/testdata/start_api/lambda_authorizers/serverless-http-props.yaml"),
        ({"AuthOverride": "Token"}, "/testdata/start_api/lambda_authorizers/serverless-api-props.yaml"),
        ({"AuthOverride": "Request"}, "/testdata/start_api/lambda_authorizers/serverless-api-props.yaml"),
    ],
)
class TestSfnPropertiesLambdaAuthorizers(StartApiIntegBaseClass):
    def setUp(self):
        self.url = f"http://127.0.0.1:{self.port}"

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_invokes_authorizer(self):
        headers = {"header": "myheader"}
        query = {"query": "myquery"}
        response = requests.get(f"{self.url}/requestauthorizer", headers=headers, params=query, timeout=300)

        response_json = response.json()
        self.assertEqual(response.status_code, 200)
        # check if the authorizer passes along a message
        self.assertEqual(response_json, {"message": "from authorizer"})

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_missing_identity_sources(self):
        response = requests.get(f"{self.url}/requestauthorizer", timeout=300)

        response_json = response.json()
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response_json, {"message": "Unauthorized"})


@parameterized_class(
    ("parameter_overrides", "template_path"),
    [
        (
            {"AuthHandler": "app.unauth", "AuthOverride": "RequestAuthorizerV1"},
            "/testdata/start_api/lambda_authorizers/serverless-http-props.yaml",
        ),
        (
            {"AuthSimpleHandler": "app.unauthv2", "AuthOverride": "RequestAuthorizerV2Simple"},
            "/testdata/start_api/lambda_authorizers/serverless-http-props.yaml",
        ),
        (
            {"AuthHandler": "app.unauth", "AuthOverride": "Token"},
            "/testdata/start_api/lambda_authorizers/serverless-api-props.yaml",
        ),
        (
            {"AuthHandler": "app.unauth", "AuthOverride": "Request"},
            "/testdata/start_api/lambda_authorizers/serverless-api-props.yaml",
        ),
    ],
)
class TestSfnPropertiesLambdaAuthorizersUnauthorized(StartApiIntegBaseClass):
    def setUp(self):
        self.url = f"http://127.0.0.1:{self.port}"

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_unauthorized_request(self):
        headers = {"header": "myheader"}
        query = {"query": "myquery"}

        response = requests.get(f"{self.url}/requestauthorizer", headers=headers, params=query, timeout=300)
        response_json = response.json()

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response_json, {"message": "User is not authorized to access this resource"})


@parameterized_class(
    ("parameter_overrides", "template_path"),
    [
        (
            {"AuthHandler": "app.throws_exception", "AuthOverride": "RequestAuthorizerV1"},
            "/testdata/start_api/lambda_authorizers/serverless-http-props.yaml",
        ),
        (
            {"AuthSimpleHandler": "app.throws_exception", "AuthOverride": "RequestAuthorizerV2Simple"},
            "/testdata/start_api/lambda_authorizers/serverless-http-props.yaml",
        ),
        (
            {"AuthHandler": "app.throws_exception", "AuthOverride": "Token"},
            "/testdata/start_api/lambda_authorizers/serverless-api-props.yaml",
        ),
        (
            {"AuthHandler": "app.throws_exception", "AuthOverride": "Request"},
            "/testdata/start_api/lambda_authorizers/serverless-api-props.yaml",
        ),
    ],
)
class TestSfnPropertiesLambdaAuthorizer500(StartApiIntegBaseClass):
    def setUp(self):
        self.url = f"http://127.0.0.1:{self.port}"

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_unauthorized_request(self):
        headers = {"header": "myheader"}
        query = {"query": "myquery"}

        response = requests.get(f"{self.url}/requestauthorizer", headers=headers, params=query, timeout=300)
        response_json = response.json()

        self.assertEqual(response.status_code, 502)
        self.assertEqual(response_json, {"message": "Internal server error"})


class TestUsingSimpleResponseWithV1HttpApi(WritableStartApiIntegBaseClass):
    do_collect_cmd_init_output = True
    template_content = """AWSTemplateFormatVersion: '2010-09-09'
Transform: AWS::Serverless-2016-10-31

Resources:
  TestServerlessHttpApi:
    Type: AWS::Serverless::HttpApi
    Properties:
      StageName: http
      Auth:
        DefaultAuthorizer: RequestAuthorizerV2
        Authorizers:
          RequestAuthorizerV2:
            AuthorizerPayloadFormatVersion: "1.0"
            EnableSimpleResponses: true
            FunctionArn: !GetAtt AuthorizerFunction.Arn
            Identity:
              Headers:
                - header
              QueryStrings:
                - query
  HelloWorldFunction:
    Type: AWS::Serverless::Function
    Properties:
      CodeUri: ./
      Handler: app.lambda_handler
      Events:
        ApiEvent:
          Type: HttpApi
          Properties:
            Path: /requestauthorizer
            Method: get
            ApiId: !Ref TestServerlessHttpApi
"""

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=10, method="thread")
    def test_invalid_template(self):
        self.assertIn(
            "EnableSimpleResponses must be used with the 2.0 payload "
            "format version in Lambda Authorizer 'RequestAuthorizerV2'.",
            self.start_api_process_output,
        )


class TestInvalidInvalidVersionHttpApi(WritableStartApiIntegBaseClass):
    """
    Test using an invalid AuthorizerPayloadFormatVersion property value
    when defining a Lambda Authorizer in the a Serverless resource properties.
    """

    do_collect_cmd_init_output = True
    template_content = """AWSTemplateFormatVersion: '2010-09-09'
Transform: AWS::Serverless-2016-10-31

Resources:
  TestServerlessHttpApi:
    Type: AWS::Serverless::HttpApi
    Properties:
      StageName: http
      Auth:
        DefaultAuthorizer: RequestAuthorizerV2
        Authorizers:
          RequestAuthorizerV2:
            AuthorizerPayloadFormatVersion: "3.0"
            EnableSimpleResponses: false
            FunctionArn: !GetAtt AuthorizerFunction.Arn
            Identity:
              Headers:
                - header
              QueryStrings:
                - query
  HelloWorldFunction:
    Type: AWS::Serverless::Function
    Properties:
      CodeUri: ./
      Handler: app.lambda_handler
      Events:
        ApiEvent:
          Type: HttpApi
          Properties:
            Path: /requestauthorizer
            Method: get
            ApiId: !Ref TestServerlessHttpApi
"""

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=10, method="thread")
    def test_invalid_template(self):
        self.assertIn(
            "Error: Lambda Authorizer 'RequestAuthorizerV2' must contain "
            "a valid 'AuthorizerPayloadFormatVersion' for HTTP APIs.",
            self.start_api_process_output,
        )


class TestUsingInvalidFunctionArnHttpApi(WritableStartApiIntegBaseClass):
    """
    Test using an invalid FunctionArn property value when defining
    a Lambda Authorizer in the a Serverless resource properties.
    """

    do_collect_cmd_init_output = True
    template_content = """AWSTemplateFormatVersion: '2010-09-09'
Transform: AWS::Serverless-2016-10-31

Resources:
  TestServerlessHttpApi:
    Type: AWS::Serverless::HttpApi
    Properties:
      StageName: http
      Auth:
        DefaultAuthorizer: RequestAuthorizerV2
        Authorizers:
          RequestAuthorizerV2:
            AuthorizerPayloadFormatVersion: "2.0"
            EnableSimpleResponses: false
            FunctionArn: iofaqio'hfw;iqauh
            Identity:
              Headers:
                - header
              QueryStrings:
                - query
  HelloWorldFunction:
    Type: AWS::Serverless::Function
    Properties:
      CodeUri: ./
      Handler: app.lambda_handler
      Events:
        ApiEvent:
          Type: HttpApi
          Properties:
            Path: /requestauthorizer
            Method: get
            ApiId: !Ref TestServerlessHttpApi
"""

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=10, method="thread")
    def test_invalid_template(self):
        self.assertIn(
            "Unable to parse the Lambda ARN for Authorizer 'RequestAuthorizerV2', skipping",
            self.start_api_process_output,
        )
