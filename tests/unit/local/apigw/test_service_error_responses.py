from unittest import TestCase
from unittest.mock import patch, Mock

from samcli.local.apigw.service_error_responses import ServiceErrorResponses


class TestServiceErrorResponses(TestCase):
    @patch("samcli.local.apigw.service_error_responses.make_response")
    @patch("samcli.local.apigw.service_error_responses.jsonify")
    def test_lambda_failure_response(self, jsonify_patch, make_response_patch):
        jsonify_patch.return_value = {"json": "Response"}
        make_response_patch.return_value = {"Some Response"}

        response = ServiceErrorResponses.lambda_failure_response()

        self.assertEqual(response, {"Some Response"})

        jsonify_patch.assert_called_with({"message": "Internal server error"})
        make_response_patch.assert_called_with({"json": "Response"}, 502)

    @patch("samcli.local.apigw.service_error_responses.make_response")
    @patch("samcli.local.apigw.service_error_responses.jsonify")
    def test_lambda_not_found_response(self, jsonify_patch, make_response_patch):
        jsonify_patch.return_value = {"json": "Response"}
        make_response_patch.return_value = {"Some Response"}
        error_mock = Mock()

        response = ServiceErrorResponses.lambda_not_found_response(error_mock)

        self.assertEqual(response, {"Some Response"})

        jsonify_patch.assert_called_with({"message": "No function defined for resource method"})
        make_response_patch.assert_called_with({"json": "Response"}, 502)

    @patch("samcli.local.apigw.service_error_responses.make_response")
    @patch("samcli.local.apigw.service_error_responses.jsonify")
    def test_route_not_found(self, jsonify_patch, make_response_patch):
        jsonify_patch.return_value = {"json": "Response"}
        make_response_patch.return_value = {"Some Response"}
        error_mock = Mock()

        response = ServiceErrorResponses.route_not_found(error_mock)

        self.assertEqual(response, {"Some Response"})

        jsonify_patch.assert_called_with({"message": "Missing Authentication Token"})
        make_response_patch.assert_called_with({"json": "Response"}, 403)

    @patch("samcli.local.apigw.service_error_responses.make_response")
    @patch("samcli.local.apigw.service_error_responses.jsonify")
    def test_lambda_failure_response_applies_gateway_response_headers(self, jsonify_patch, make_response_patch):
        response_mock = Mock()
        make_response_patch.return_value = response_mock

        headers = {"Access-Control-Allow-Origin": "*"}
        response = ServiceErrorResponses.lambda_failure_response(headers=headers)

        self.assertEqual(response, response_mock)
        response_mock.headers.update.assert_called_once_with(headers)

    @patch("samcli.local.apigw.service_error_responses.make_response")
    @patch("samcli.local.apigw.service_error_responses.jsonify")
    def test_lambda_body_failure_response_applies_gateway_response_headers(self, jsonify_patch, make_response_patch):
        response_mock = Mock()
        make_response_patch.return_value = response_mock

        headers = {"Access-Control-Allow-Origin": "*"}
        response = ServiceErrorResponses.lambda_body_failure_response(headers=headers)

        self.assertEqual(response, response_mock)
        response_mock.headers.update.assert_called_once_with(headers)

    @patch("samcli.local.apigw.service_error_responses.make_response")
    @patch("samcli.local.apigw.service_error_responses.jsonify")
    def test_lambda_authorizer_unauthorized_applies_gateway_response_headers(self, jsonify_patch, make_response_patch):
        response_mock = Mock()
        make_response_patch.return_value = response_mock

        headers = {"Access-Control-Allow-Origin": "*"}
        response = ServiceErrorResponses.lambda_authorizer_unauthorized(headers=headers)

        self.assertEqual(response, response_mock)
        response_mock.headers.update.assert_called_once_with(headers)

    @patch("samcli.local.apigw.service_error_responses.make_response")
    @patch("samcli.local.apigw.service_error_responses.jsonify")
    def test_missing_lambda_auth_identity_sources_applies_gateway_response_headers(
        self, jsonify_patch, make_response_patch
    ):
        response_mock = Mock()
        make_response_patch.return_value = response_mock

        headers = {"Access-Control-Allow-Origin": "*"}
        response = ServiceErrorResponses.missing_lambda_auth_identity_sources(headers=headers)

        self.assertEqual(response, response_mock)
        response_mock.headers.update.assert_called_once_with(headers)

    @patch("samcli.local.apigw.service_error_responses.make_response")
    @patch("samcli.local.apigw.service_error_responses.jsonify")
    def test_no_headers_leaves_response_untouched(self, jsonify_patch, make_response_patch):
        response_mock = Mock()
        make_response_patch.return_value = response_mock

        ServiceErrorResponses.lambda_failure_response()

        response_mock.headers.update.assert_not_called()

    @patch("samcli.local.apigw.service_error_responses.make_response")
    @patch("samcli.local.apigw.service_error_responses.jsonify")
    def test_lambda_not_found_response_applies_gateway_response_headers(self, jsonify_patch, make_response_patch):
        response_mock = Mock()
        make_response_patch.return_value = response_mock

        headers = {"Access-Control-Allow-Origin": "*"}
        response = ServiceErrorResponses.lambda_not_found_response(headers=headers)

        self.assertEqual(response, response_mock)
        response_mock.headers.update.assert_called_once_with(headers)

    @patch("samcli.local.apigw.service_error_responses.make_response")
    @patch("samcli.local.apigw.service_error_responses.jsonify")
    def test_not_implemented_locally_applies_gateway_response_headers(self, jsonify_patch, make_response_patch):
        response_mock = Mock()
        make_response_patch.return_value = response_mock

        headers = {"Access-Control-Allow-Origin": "*"}
        response = ServiceErrorResponses.not_implemented_locally("message", headers=headers)

        self.assertEqual(response, response_mock)
        response_mock.headers.update.assert_called_once_with(headers)

    @patch("samcli.local.apigw.service_error_responses.make_response")
    @patch("samcli.local.apigw.service_error_responses.jsonify")
    def test_container_creation_failed_applies_gateway_response_headers(self, jsonify_patch, make_response_patch):
        response_mock = Mock()
        make_response_patch.return_value = response_mock

        headers = {"Access-Control-Allow-Origin": "*"}
        response = ServiceErrorResponses.container_creation_failed("message", headers=headers)

        self.assertEqual(response, response_mock)
        response_mock.headers.update.assert_called_once_with(headers)

    @patch("samcli.local.apigw.service_error_responses.make_response")
    @patch("samcli.local.apigw.service_error_responses.jsonify")
    def test_tenant_id_validation_error_applies_gateway_response_headers(self, jsonify_patch, make_response_patch):
        response_mock = Mock()
        make_response_patch.return_value = response_mock

        headers = {"Access-Control-Allow-Origin": "*"}
        response = ServiceErrorResponses.tenant_id_validation_error("message", headers=headers)

        self.assertEqual(response, response_mock)
        response_mock.headers.update.assert_called_once_with(headers)
