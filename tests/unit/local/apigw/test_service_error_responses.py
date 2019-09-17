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
