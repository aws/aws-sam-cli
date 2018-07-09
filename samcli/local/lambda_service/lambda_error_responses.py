""" Common Lambda Error Response"""

import json

from samcli.local.services.base_local_service import BaseLocalService


class LambdaErrorResponses(object):

    # The content type of the Invoke request body is not JSON.
    UnsupportedMediaTypeException = ('UnsupportedMediaType', 415)

    # The AWS Lambda service encountered an internal error.
    ServiceException = ('Service', 500)

    # The resource (for example, a Lambda function or access policy statement) specified in the request does not exist.
    ResourceNotFoundException = ('ResourceNotFound', 404)

    # The request body could not be parsed as JSON.
    InvalidRequestContentException = ('InvalidRequestContent', 400)

    # Error Types
    USER_ERROR = "User"
    SERVICE_ERROR = "Service"
    LOCAL_SERVICE_ERROR = "LocalService"

    # Header Information
    CONTENT_TYPE = 'application/json'
    CONTENT_TYPE_HEADER_KEY = 'Content-Type'


    @staticmethod
    def resource_not_found(function_name):
        """

        Parameters
        ----------
        function_name

        Returns
        -------

        """
        return BaseLocalService._service_response(LambdaErrorResponses._construct_error_response_body(LambdaErrorResponses.USER_ERROR, "Function not found: arn:aws:lambda:us-west-2:012345678901:function:{}".format(function_name)),
            {'x-amzn-errortype': LambdaErrorResponses.ResourceNotFoundException[0], 'Content-Type': 'application/json'},
            LambdaErrorResponses.ResourceNotFoundException[1])

    @staticmethod
    def invalid_request_content(message):
        return BaseLocalService._service_response(LambdaErrorResponses._construct_error_response_body(LambdaErrorResponses.USER_ERROR, message),
            {'x-amzn-errortype': 'InvalidRequestContentException', 'Content-Type': 'application/json'},
            400
        )

    @staticmethod
    def unsupported_media_type(content_type):
        return BaseLocalService._service_response(LambdaErrorResponses._construct_error_response_body(LambdaErrorResponses.USER_ERROR, "Unsupported content type: {}".format(content_type)),
            {'x-amzn-errortype': 'UnsupportedMediaType', 'Content-Type': 'application/json'},
            415
        )

    @staticmethod
    def generic_service_exception(*args):
        return BaseLocalService._service_response(LambdaErrorResponses._construct_error_response_body(LambdaErrorResponses.SERVICE_ERROR, "ServiceException"),
            {'x-amzn-errortype': 'ServiceException', 'Content-Type': 'application/json'},
            500
        )

    @staticmethod
    def not_implemented_locally(message):
        return BaseLocalService._service_response(LambdaErrorResponses._construct_error_response_body(LambdaErrorResponses.LOCAL_SERVICE_ERROR, message),
            {'x-amzn-errortype': 'NotImplemented', 'Content-Type': 'application/json'},
            501
        )

    @staticmethod
    def generic_path_not_found(*args):
        return BaseLocalService._service_response(
            LambdaErrorResponses._construct_error_response_body(LambdaErrorResponses.LOCAL_SERVICE_ERROR, "PathNotFoundException"),
            {'x-amzn-errortype': 'LocalServiceException', 'Content-Type': 'application/json'},
            404
        )

    @staticmethod
    def generic_method_not_allowed(*args):
        return BaseLocalService._service_response(
            LambdaErrorResponses._construct_error_response_body(LambdaErrorResponses.LOCAL_SERVICE_ERROR,
                                                               "MethodNotAllowedException"),
            {'x-amzn-errortype': 'LocalServiceException', 'Content-Type': 'application/json'},
            405
        )

    @staticmethod
    def _construct_error_response_body(error_type, error_message):
        return json.dumps({"Type": error_type, "Message": error_message})
