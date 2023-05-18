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
        ("/testdata/start_api/lambda_authorizers/swagger-api.yaml", "requestauthorizerswaggertoken", {}),
        (
            "/testdata/start_api/lambda_authorizers/swagger-api.yaml",
            "requestauthorizerswaggertoken",
            {"ValidationString": "^myheader$"},
        ),
        ("/testdata/start_api/lambda_authorizers/swagger-api.yaml", "requestauthorizerswaggerrequest", {}),
        ("/testdata/start_api/lambda_authorizers/swagger-api.yaml", "requestauthorizeropenapi", {}),
        ("/testdata/start_api/lambda_authorizers/swagger-http.yaml", "requestauthorizer", {}),
        (
            "/testdata/start_api/lambda_authorizers/swagger-http.yaml",
            "requestauthorizersimple",
            {"AuthHandler": "app.simple_handler"},
        ),
        (
            "/testdata/start_api/lambda_authorizers/swagger-api.yaml",
            "requestauthorizerswaggerrequest/authorized",
            {"AuthHandler": "app.auth_handler_swagger_parameterized"},
        ),
        (
            "/testdata/start_api/lambda_authorizers/swagger-api.yaml",
            "requestauthorizerswaggertoken/authorized",
            {"AuthHandler": "app.auth_handler_swagger_parameterized"},
        ),
    ],
)
class TestSwaggerLambdaAuthorizerResources(StartApiIntegBaseClass):
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
            "/testdata/start_api/lambda_authorizers/swagger-api.yaml",
            "requestauthorizerswaggertoken",
            {"AuthHandler": "app.unauth"},
        ),
        (
            "/testdata/start_api/lambda_authorizers/swagger-api.yaml",
            "requestauthorizerswaggerrequest",
            {"AuthHandler": "app.unauth"},
        ),
        (
            "/testdata/start_api/lambda_authorizers/swagger-api.yaml",
            "requestauthorizeropenapi",
            {"AuthHandler": "app.unauth"},
        ),
        (
            "/testdata/start_api/lambda_authorizers/swagger-http.yaml",
            "requestauthorizer",
            {"AuthHandler": "app.unauth"},
        ),
        (
            "/testdata/start_api/lambda_authorizers/swagger-http.yaml",
            "requestauthorizersimple",
            {"AuthHandler": "app.unauthv2"},
        ),
        (
            "/testdata/start_api/lambda_authorizers/swagger-api.yaml",
            "requestauthorizerswaggerrequest/unauthorized",
            {"AuthHandler": "app.auth_handler_swagger_parameterized"},
        ),
        (
            "/testdata/start_api/lambda_authorizers/swagger-api.yaml",
            "requestauthorizerswaggertoken/unauthorized",
            {"AuthHandler": "app.auth_handler_swagger_parameterized"},
        ),
    ],
)
class TestSwaggerLambdaAuthorizersUnauthorized(StartApiIntegBaseClass):
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
        ("/testdata/start_api/lambda_authorizers/swagger-api.yaml", "requestauthorizerswaggertoken"),
        ("/testdata/start_api/lambda_authorizers/swagger-api.yaml", "requestauthorizerswaggerrequest"),
        ("/testdata/start_api/lambda_authorizers/swagger-api.yaml", "requestauthorizeropenapi"),
        ("/testdata/start_api/lambda_authorizers/swagger-http.yaml", "requestauthorizer"),
        ("/testdata/start_api/lambda_authorizers/swagger-http.yaml", "requestauthorizersimple"),
    ],
)
class TestSwaggerLambdaAuthorizer500(StartApiIntegBaseClass):
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


class TestInvalidSwaggerTemplateUsingUnsupportedType(WritableStartApiIntegBaseClass):
    """
    Test using an invalid Lambda authorizer type
    """

    do_collect_cmd_init_output = True

    template_content = """AWSTemplateFormatVersion: '2010-09-09'
Transform: AWS::Serverless-2016-10-31

Resources:
  HttpApiOpenApi:
    Type: AWS::ApiGatewayV2::Api
    Properties:
      Body:
        openapi: "3.0"
        info:
          title: HttpApiOpenApi
        components:
          securitySchemes:
            Authorizer:
              type: apiKey
              in: header
              name: notused
              "x-amazon-apigateway-authorizer":
                authorizerPayloadFormatVersion: "2.0"
                type: "bad type"
                identitySource: "$request.header.header, $request.querystring.query"
                authorizerUri: arn:aws:apigateway:us-east-1:lambda:path/2015-03-31/functions/arn:aws:lambda:us-east-1:123456789012:function:AuthorizerFunction/invocations
"""

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=10, method="thread")
    def test_invalid_template(self):
        self.assertIn(
            "Lambda authorizer 'Authorizer' type 'bad type' is unsupported, skipping",
            self.start_api_process_output,
        )


class TestInvalidSwaggerTemplateUsingSimpleResponseWithPayloadV1(WritableStartApiIntegBaseClass):
    """
    Test using simple response with wrong payload version
    """

    do_collect_cmd_init_output = True

    template_content = """AWSTemplateFormatVersion: '2010-09-09'
Transform: AWS::Serverless-2016-10-31

Resources:
  HttpApiOpenApi:
    Type: AWS::ApiGatewayV2::Api
    Properties:
      Body:
        openapi: "3.0"
        info:
          title: HttpApiOpenApi
        components:
          securitySchemes:
            Authorizer:
              type: apiKey
              in: header
              name: notused
              "x-amazon-apigateway-authorizer":
                authorizerPayloadFormatVersion: "1.0"
                type: "request"
                enableSimpleResponses: True
                identitySource: "$request.header.header, $request.querystring.query"
                authorizerUri: arn:aws:apigateway:us-east-1:lambda:path/2015-03-31/functions/arn:aws:lambda:us-east-1:123456789012:function:AuthorizerFunction/invocations
"""

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=10, method="thread")
    def test_invalid_template(self):
        self.assertIn(
            "Simple responses are only available on HTTP APIs with "
            "payload version 2.0, ignoring for Lambda authorizer 'Authorizer'",
            self.start_api_process_output,
        )


class TestInvalidSwaggerTemplateUsingUnsupportedPayloadVersion(WritableStartApiIntegBaseClass):
    """
    Test using an incorrect payload format version
    """

    do_collect_cmd_init_output = True

    template_content = """AWSTemplateFormatVersion: '2010-09-09'
Transform: AWS::Serverless-2016-10-31

Resources:
  HttpApiOpenApi:
    Type: AWS::ApiGatewayV2::Api
    Properties:
      Body:
        openapi: "3.0"
        info:
          title: HttpApiOpenApi
        components:
          securitySchemes:
            Authorizer:
              type: apiKey
              in: header
              name: notused
              "x-amazon-apigateway-authorizer":
                authorizerPayloadFormatVersion: "1.2.3"
                type: "request"
                identitySource: "$request.header.header, $request.querystring.query"
                authorizerUri: arn:aws:apigateway:us-east-1:lambda:path/2015-03-31/functions/arn:aws:lambda:us-east-1:123456789012:function:AuthorizerFunction/invocations
"""

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=10, method="thread")
    def test_invalid_template(self):
        self.assertIn(
            "Error: Authorizer 'Authorizer' contains an invalid payload version",
            self.start_api_process_output,
        )


class TestInvalidSwaggerTemplateUsingInvalidIdentitySources(WritableStartApiIntegBaseClass):
    """
    Test using an invalid identity source (a.b.c.d.e)
    """

    do_collect_cmd_init_output = True

    template_content = """AWSTemplateFormatVersion: '2010-09-09'
Transform: AWS::Serverless-2016-10-31

Resources:
  HttpApiOpenApi:
    Type: AWS::ApiGatewayV2::Api
    Properties:
      Body:
        openapi: "3.0"
        info:
          title: HttpApiOpenApi
        components:
          securitySchemes:
            Authorizer:
              type: apiKey
              in: header
              name: notused
              "x-amazon-apigateway-authorizer":
                authorizerPayloadFormatVersion: "2.0"
                type: "request"
                identitySource: "a.b.c.d.e"
                authorizerUri: arn:aws:apigateway:us-east-1:lambda:path/2015-03-31/functions/arn:aws:lambda:us-east-1:123456789012:function:AuthorizerFunction/invocations
"""

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=10, method="thread")
    def test_invalid_template(self):
        self.assertIn(
            "Error: Identity source 'a.b.c.d.e' for Lambda Authorizer "
            "'Authorizer' is not a valid identity source, check the spelling/format.",
            self.start_api_process_output,
        )


class TestInvalidSwaggerTemplateUsingTokenWithHttpApi(WritableStartApiIntegBaseClass):
    """
    Test using token authorizer with HTTP API
    """

    do_collect_cmd_init_output = True

    template_content = """AWSTemplateFormatVersion: '2010-09-09'
Transform: AWS::Serverless-2016-10-31

Resources:
  HttpApiOpenApi:
    Type: AWS::ApiGatewayV2::Api
    Properties:
      Body:
        openapi: "3.0"
        info:
          title: HttpApiOpenApi
        components:
          securitySchemes:
            Authorizer:
              type: apiKey
              in: header
              name: notused
              "x-amazon-apigateway-authorizer":
                authorizerPayloadFormatVersion: "2.0"
                type: "token"
                identitySource: "$request.header.header"
                authorizerUri: arn:aws:apigateway:us-east-1:lambda:path/2015-03-31/functions/arn:aws:lambda:us-east-1:123456789012:function:AuthorizerFunction/invocations
"""

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=10, method="thread")
    def test_invalid_template(self):
        self.assertIn(
            "Type 'token' for Lambda Authorizer 'Authorizer' is unsupported",
            self.start_api_process_output,
        )
