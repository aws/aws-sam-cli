import pytest
import requests
from tests.integration.local.start_api.start_api_integ_base import (
    StartApiIntegBaseClass,
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
