from unittest import TestCase
from unittest.mock import patch

from samcli.local.lambda_service.lambda_error_responses import LambdaErrorResponses


class TestLambdaErrorResponses(TestCase):
    @patch("samcli.local.services.base_local_service.BaseLocalService.service_response")
    def test_resource_not_found(self, service_response_mock):
        service_response_mock.return_value = "ResourceNotFound"

        response = LambdaErrorResponses.resource_not_found("HelloFunction")

        self.assertEqual(response, "ResourceNotFound")
        service_response_mock.assert_called_once_with(
            '{"Type": "User", "Message": "Function not found: '
            'arn:aws:lambda:us-west-2:012345678901:function:HelloFunction"}',
            {"x-amzn-errortype": "ResourceNotFound", "Content-Type": "application/json"},
            404,
        )

    @patch("samcli.local.services.base_local_service.BaseLocalService.service_response")
    def test_invalid_request_content(self, service_response_mock):
        service_response_mock.return_value = "InvalidRequestContent"

        response = LambdaErrorResponses.invalid_request_content("InvalidRequestContent")

        self.assertEqual(response, "InvalidRequestContent")
        service_response_mock.assert_called_once_with(
            '{"Type": "User", "Message": "InvalidRequestContent"}',
            {"x-amzn-errortype": "InvalidRequestContent", "Content-Type": "application/json"},
            400,
        )

    @patch("samcli.local.services.base_local_service.BaseLocalService.service_response")
    def test_unsupported_media_type(self, service_response_mock):
        service_response_mock.return_value = "UnsupportedMediaType"

        response = LambdaErrorResponses.unsupported_media_type("UnsupportedMediaType")

        self.assertEqual(response, "UnsupportedMediaType")
        service_response_mock.assert_called_once_with(
            '{"Type": "User", "Message": "Unsupported content type: UnsupportedMediaType"}',
            {"x-amzn-errortype": "UnsupportedMediaType", "Content-Type": "application/json"},
            415,
        )

    @patch("samcli.local.services.base_local_service.BaseLocalService.service_response")
    def test_generic_service_exception(self, service_response_mock):
        service_response_mock.return_value = "GenericServiceException"

        response = LambdaErrorResponses.generic_service_exception("GenericServiceException")

        self.assertEqual(response, "GenericServiceException")
        service_response_mock.assert_called_once_with(
            '{"Type": "Service", "Message": "ServiceException"}',
            {"x-amzn-errortype": "Service", "Content-Type": "application/json"},
            500,
        )

    @patch("samcli.local.services.base_local_service.BaseLocalService.service_response")
    def test_not_implemented_locally(self, service_response_mock):
        service_response_mock.return_value = "NotImplementedLocally"

        response = LambdaErrorResponses.not_implemented_locally("NotImplementedLocally")

        self.assertEqual(response, "NotImplementedLocally")
        service_response_mock.assert_called_once_with(
            '{"Type": "LocalService", "Message": "NotImplementedLocally"}',
            {"x-amzn-errortype": "NotImplemented", "Content-Type": "application/json"},
            501,
        )

    @patch("samcli.local.services.base_local_service.BaseLocalService.service_response")
    def test_generic_path_not_found(self, service_response_mock):
        service_response_mock.return_value = "GenericPathNotFound"

        response = LambdaErrorResponses.generic_path_not_found("GenericPathNotFound")

        self.assertEqual(response, "GenericPathNotFound")
        service_response_mock.assert_called_once_with(
            '{"Type": "LocalService", "Message": "PathNotFoundException"}',
            {"x-amzn-errortype": "PathNotFoundLocally", "Content-Type": "application/json"},
            404,
        )

    @patch("samcli.local.services.base_local_service.BaseLocalService.service_response")
    def test_generic_method_not_allowed(self, service_response_mock):
        service_response_mock.return_value = "GenericMethodNotAllowed"

        response = LambdaErrorResponses.generic_method_not_allowed("GenericMethodNotAllowed")

        self.assertEqual(response, "GenericMethodNotAllowed")
        service_response_mock.assert_called_once_with(
            '{"Type": "LocalService", "Message": "MethodNotAllowedException"}',
            {"x-amzn-errortype": "MethodNotAllowedLocally", "Content-Type": "application/json"},
            405,
        )
