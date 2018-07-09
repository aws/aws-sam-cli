"""Common Lambda Error Responses"""

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
        Creates a Lambda Service ResourceNotFound Response

        Parameters
        ----------
        function_name str
            Name of the function that was requested to invoke

        Returns
        -------
        Flask.Response
            A response object representing the ResourceNotFound Error
        """
        return BaseLocalService.service_response(
            LambdaErrorResponses._construct_error_response_body(
                LambdaErrorResponses.USER_ERROR,
                "Function not found: arn:aws:lambda:us-west-2:012345678901:function:{}".format(function_name)
            ),
            {'x-amzn-errortype': LambdaErrorResponses.ResourceNotFoundException[0], 'Content-Type': 'application/json'},
            LambdaErrorResponses.ResourceNotFoundException[1])

    @staticmethod
    def invalid_request_content(message):
        """
        Creates a Lambda Service InvalidRequestContent Response

        Parameters
        ----------
        message str
            Message to be added to the body of the response

        Returns
        -------
        Flask.Response
            A response object representing the InvalidRequestContent Error
        """
        return BaseLocalService.service_response(
            LambdaErrorResponses._construct_error_response_body(LambdaErrorResponses.USER_ERROR, message),
            {'x-amzn-errortype': 'InvalidRequestContentException', 'Content-Type': 'application/json'},
            400
        )

    @staticmethod
    def unsupported_media_type(content_type):
        """
        Creates a Lambda Service UnsupportedMediaType Response

        Parameters
        ----------
        content_type str
            Content Type of the request that was made

        Returns
        -------
        Flask.Response
            A response object representing the UnsupportedMediaType Error
        """
        return BaseLocalService.service_response(
            LambdaErrorResponses._construct_error_response_body(LambdaErrorResponses.USER_ERROR,
                                                                "Unsupported content type: {}".format(content_type)),
            {'x-amzn-errortype': 'UnsupportedMediaType', 'Content-Type': 'application/json'},
            415
        )

    @staticmethod
    def generic_service_exception(*args):
        """
        Creates a Lambda Service Generic ServiceException Response

        Parameters
        ----------
        args list
            List of arguments Flask passes to the method

        Returns
        -------
        Flask.Response
            A response object representing the GenericServiceException Error
        """
        return BaseLocalService.service_response(
            LambdaErrorResponses._construct_error_response_body(LambdaErrorResponses.SERVICE_ERROR, "ServiceException"),
            {'x-amzn-errortype': 'ServiceException', 'Content-Type': 'application/json'},
            500
        )

    @staticmethod
    def not_implemented_locally(message):
        """
        Creates a Lambda Service NotImplementedLocally Response

        Parameters
        ----------
        message str
            Message to be added to the body of the response

        Returns
        -------
        Flask.Response
            A response object representing the NotImplementedLocally Error
        """
        return BaseLocalService.service_response(
            LambdaErrorResponses._construct_error_response_body(LambdaErrorResponses.LOCAL_SERVICE_ERROR, message),
            {'x-amzn-errortype': 'NotImplemented', 'Content-Type': 'application/json'},
            501
        )

    @staticmethod
    def generic_path_not_found(*args):
        """
        Creates a Lambda Service Generic PathNotFound Response

        Parameters
        ----------
        args list
            List of arguments Flask passes to the method

        Returns
        -------
        Flask.Response
            A response object representing the GenericPathNotFound Error
        """
        return BaseLocalService.service_response(
            LambdaErrorResponses._construct_error_response_body(
                LambdaErrorResponses.LOCAL_SERVICE_ERROR, "PathNotFoundException"),
            {'x-amzn-errortype': 'LocalServiceException', 'Content-Type': 'application/json'},
            404
        )

    @staticmethod
    def generic_method_not_allowed(*args):
        """
        Creates a Lambda Service Generic MethodNotAllowed Response

        Parameters
        ----------
        args list
            List of arguments Flask passes to the method

        Returns
        -------
        Flask.Response
            A response object representing the GenericMethodNotAllowed Error
        """
        return BaseLocalService.service_response(
            LambdaErrorResponses._construct_error_response_body(LambdaErrorResponses.LOCAL_SERVICE_ERROR,
                                                                "MethodNotAllowedException"),
            {'x-amzn-errortype': 'LocalServiceException', 'Content-Type': 'application/json'},
            405
        )

    @staticmethod
    def _construct_error_response_body(error_type, error_message):
        """
        Constructs a string to be used in the body of the Response that conforms
        to the structure of the Lambda Service Responses

        Parameters
        ----------
        error_type str
            The type of error
        error_message str
            Message of the error that occured

        Returns
        -------
        str
            str representing the response body
        """
        return json.dumps({"Type": error_type, "Message": error_message})
