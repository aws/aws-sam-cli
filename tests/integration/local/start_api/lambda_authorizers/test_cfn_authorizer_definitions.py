import pytest
import requests
from tests.integration.local.start_api.start_api_integ_base import (
    StartApiIntegBaseClass,
    WritableStartApiIntegBaseClass,
)
from parameterized import parameterized_class


@parameterized_class(
    ("template_path", "endpoint", "parameter_overrides"),
    [
        ("/testdata/start_api/lambda_authorizers/cfn-apigw-v1.yaml", "requestauthorizertoken", {}),
        ("/testdata/start_api/lambda_authorizers/cfn-apigw-v1.yaml", "requestauthorizerrequest", {}),
        (
            "/testdata/start_api/lambda_authorizers/cfn-apigw-v2.yaml",
            "requestauthorizerv2",
            {"RoutePayloadFormatVersion": "2.0"},
        ),
        (
            "/testdata/start_api/lambda_authorizers/cfn-apigw-v2.yaml",
            "requestauthorizerv2",
            {"RoutePayloadFormatVersion": "1.0"},
        ),
        (
            "/testdata/start_api/lambda_authorizers/cfn-apigw-v2.yaml",
            "requestauthorizerv2simple",
            {"AuthHandler": "app.simple_handler", "RoutePayloadFormatVersion": "2.0"},
        ),
        (
            "/testdata/start_api/lambda_authorizers/cfn-apigw-v2.yaml",
            "requestauthorizerv2simple",
            {"AuthHandler": "app.simple_handler", "RoutePayloadFormatVersion": "1.0"},
        ),
        (
            "/testdata/start_api/lambda_authorizers/cfn-apigw-v2.yaml",
            "requestauthorizerv1",
            {"RoutePayloadFormatVersion": "2.0"},
        ),
        (
            "/testdata/start_api/lambda_authorizers/cfn-apigw-v2.yaml",
            "requestauthorizerv1",
            {"RoutePayloadFormatVersion": "1.0"},
        ),
    ],
)
class TestCfnLambdaAuthorizerResources(StartApiIntegBaseClass):
    def setUp(self):
        self.url = f"http://127.0.0.1:{self.port}"

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_invokes_authorizer(self):
        headers = {"header": "myheader"}
        query_string = {"query": "myquery"}

        response = requests.get(f"{self.url}/{self.endpoint}", headers=headers, params=query_string, timeout=300)
        response_json = response.json()

        self.assertEqual(response.status_code, 200)
        # check if the authorizer passes along a message
        self.assertEqual(response_json, {"message": "from authorizer"})

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_missing_identity_sources(self):
        response = requests.get(f"{self.url}/{self.endpoint}", timeout=300)

        response_json = response.json()
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response_json, {"message": "Unauthorized"})


@parameterized_class(
    ("template_path", "endpoint", "parameter_overrides"),
    [
        (
            "/testdata/start_api/lambda_authorizers/cfn-apigw-v1.yaml",
            "requestauthorizertoken",
            {"AuthHandler": "app.unauth"},
        ),
        (
            "/testdata/start_api/lambda_authorizers/cfn-apigw-v1.yaml",
            "requestauthorizerrequest",
            {"AuthHandler": "app.unauth"},
        ),
        (
            "/testdata/start_api/lambda_authorizers/cfn-apigw-v2.yaml",
            "requestauthorizerv2",
            {"AuthHandler": "app.unauth"},
        ),
        (
            "/testdata/start_api/lambda_authorizers/cfn-apigw-v2.yaml",
            "requestauthorizerv2simple",
            {"AuthHandler": "app.unauthv2"},
        ),
        (
            "/testdata/start_api/lambda_authorizers/cfn-apigw-v2.yaml",
            "requestauthorizerv1",
            {"AuthHandler": "app.unauth"},
        ),
    ],
)
class TestCfnLambdaAuthorizersUnauthorized(StartApiIntegBaseClass):
    def setUp(self):
        self.url = f"http://127.0.0.1:{self.port}"

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_unauthorized_request(self):
        headers = {"header": "myheader"}
        query_string = {"query": "myquery"}

        response = requests.get(f"{self.url}/{self.endpoint}", headers=headers, params=query_string, timeout=300)
        response_json = response.json()

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response_json, {"message": "User is not authorized to access this resource"})


@parameterized_class(
    ("template_path", "endpoint"),
    [
        (
            "/testdata/start_api/lambda_authorizers/cfn-apigw-v1.yaml",
            "requestauthorizertoken",
        ),
        (
            "/testdata/start_api/lambda_authorizers/cfn-apigw-v1.yaml",
            "requestauthorizerrequest",
        ),
        (
            "/testdata/start_api/lambda_authorizers/cfn-apigw-v2.yaml",
            "requestauthorizerv2",
        ),
        (
            "/testdata/start_api/lambda_authorizers/cfn-apigw-v2.yaml",
            "requestauthorizerv2simple",
        ),
        (
            "/testdata/start_api/lambda_authorizers/cfn-apigw-v2.yaml",
            "requestauthorizerv1",
        ),
    ],
)
class TestCfnLambdaAuthorizer500(StartApiIntegBaseClass):
    parameter_overrides = {"AuthHandler": "app.throws_exception"}

    def setUp(self):
        self.url = f"http://127.0.0.1:{self.port}"

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_authorizer_raises_exception(self):
        headers = {"header": "myheader"}
        query_string = {"query": "myquery"}

        response = requests.get(f"{self.url}/{self.endpoint}", headers=headers, params=query_string, timeout=300)
        response_json = response.json()

        self.assertEqual(response.status_code, 502)
        self.assertEqual(response_json, {"message": "Internal server error"})


class TestInvalidApiTemplateUsingUnsupportedType(WritableStartApiIntegBaseClass):
    """
    Test using an invalid Type for an Authorizer
    """

    do_collect_cmd_init_output = True

    template_content = """AWSTemplateFormatVersion: '2010-09-09'
Transform: AWS::Serverless-2016-10-31

Resources:
  RequestAuthorizer:
    Type: AWS::ApiGateway::Authorizer
    Properties:
      AuthorizerUri: arn:aws:apigateway:123:lambda:path/2015-03-31/functions/arn/invocations
      Type: notvalid
      IdentitySource: "method.request.header.header, method.request.querystring.query"
      Name: RequestAuthorizer
      RestApiId: !Ref RestApiLambdaAuth
"""

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=10, method="thread")
    def test_invalid_template(self):
        self.assertIn(
            "Authorizer 'RequestAuthorizer' with type 'notvalid' is currently not supported. "
            "Only Lambda Authorizers of type TOKEN and REQUEST are supported.",
            self.start_api_process_output,
        )


class TestInvalidHttpTemplateUsingIncorrectPayloadVersion(WritableStartApiIntegBaseClass):
    """
    Test using an invalid AuthorizerPayloadFormatVersion for an Authorizer
    """

    do_collect_cmd_init_output = True

    template_content = """AWSTemplateFormatVersion: '2010-09-09'
Transform: AWS::Serverless-2016-10-31

Resources:
  RequestAuthorizerV2Simple:
    Type: AWS::ApiGatewayV2::Authorizer
    Properties:
      AuthorizerPayloadFormatVersion: "3.0"
      EnableSimpleResponses: false
      AuthorizerType: REQUEST
      AuthorizerUri: arn:aws:apigateway:us-east-1:lambda:path/2015-03-31/functions/arn:aws:lambda:us-east-1:123456789012:function:AuthorizerFunction/invocations
      IdentitySource:
        - "$request.header.header"
        - "$request.querystring.query"
      Name: RequestAuthorizerV2Simple
      ApiId: !Ref HttpLambdaAuth
"""

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=10, method="thread")
    def test_invalid_template(self):
        self.assertIn(
            "Error: Lambda Authorizer 'RequestAuthorizerV2Simple' contains an "
            "invalid 'AuthorizerPayloadFormatVersion', it must be set to '1.0' or '2.0'",
            self.start_api_process_output,
        )


class TestInvalidHttpTemplateSimpleResponseWithV1(WritableStartApiIntegBaseClass):
    """
    Test using simple responses with V1 format version
    """

    do_collect_cmd_init_output = True

    template_content = """AWSTemplateFormatVersion: '2010-09-09'
Transform: AWS::Serverless-2016-10-31

Resources:
  RequestAuthorizerV2Simple:
    Type: AWS::ApiGatewayV2::Authorizer
    Properties:
      AuthorizerPayloadFormatVersion: "1.0"
      EnableSimpleResponses: true
      AuthorizerType: REQUEST
      AuthorizerUri: arn:aws:apigateway:us-east-1:lambda:path/2015-03-31/functions/arn:aws:lambda:us-east-1:123456789012:function:AuthorizerFunction/invocations
      IdentitySource:
        - "$request.header.header"
        - "$request.querystring.query"
      Name: RequestAuthorizerV2Simple
      ApiId: !Ref HttpLambdaAuth
"""

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=10, method="thread")
    def test_invalid_template(self):
        self.assertIn(
            "Error: 'EnableSimpleResponses' is only supported for '2.0' "
            "payload format versions for Lambda Authorizer 'RequestAuthorizerV2Simple'.",
            self.start_api_process_output,
        )


class TestInvalidHttpTemplateUnsupportedType(WritableStartApiIntegBaseClass):
    """
    Test using an invalid Type for HttpApi
    """

    do_collect_cmd_init_output = True

    template_content = """AWSTemplateFormatVersion: '2010-09-09'
Transform: AWS::Serverless-2016-10-31

Resources:
  RequestAuthorizerV2Simple:
    Type: AWS::ApiGatewayV2::Authorizer
    Properties:
      AuthorizerPayloadFormatVersion: "1.0"
      EnableSimpleResponses: false
      AuthorizerType: unsupportedtype
      AuthorizerUri: arn:aws:apigateway:us-east-1:lambda:path/2015-03-31/functions/arn:aws:lambda:us-east-1:123456789012:function:AuthorizerFunction/invocations
      IdentitySource:
        - "$request.header.header"
        - "$request.querystring.query"
      Name: RequestAuthorizerV2Simple
      ApiId: !Ref HttpLambdaAuth
"""

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=10, method="thread")
    def test_invalid_template(self):
        self.assertIn(
            "Authorizer 'RequestAuthorizerV2Simple' with type 'unsupportedtype' is currently "
            "not supported. Only Lambda Authorizers of type REQUEST are supported for API Gateway V2.",
            self.start_api_process_output,
        )


class TestInvalidHttpTemplateInvalidIdentitySources(WritableStartApiIntegBaseClass):
    """
    Test using an invalid identity source
    """

    do_collect_cmd_init_output = True

    template_content = """AWSTemplateFormatVersion: '2010-09-09'
Transform: AWS::Serverless-2016-10-31

Resources:
  RequestAuthorizerV2Simple:
    Type: AWS::ApiGatewayV2::Authorizer
    Properties:
      AuthorizerPayloadFormatVersion: "1.0"
      EnableSimpleResponses: false
      AuthorizerType: REQUEST
      AuthorizerUri: arn:aws:apigateway:us-east-1:lambda:path/2015-03-31/functions/arn:aws:lambda:us-east-1:123456789012:function:AuthorizerFunction/invocations
      IdentitySource:
        - "hello.world.this.is.invalid"
      Name: RequestAuthorizerV2Simple
      ApiId: !Ref HttpLambdaAuth
"""

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=10, method="thread")
    def test_invalid_template(self):
        self.assertIn(
            "Error: Lambda Authorizer RequestAuthorizerV2Simple does not contain valid identity sources.",
            self.start_api_process_output,
        )
