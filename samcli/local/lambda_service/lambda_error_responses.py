"""Common Lambda Error Responses"""

import json
from collections import OrderedDict

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

    NotImplementedException = ('NotImplemented', 501)

    PathNotFoundException = ('PathNotFoundLocally', 404)

    MethodNotAllowedException = ('MethodNotAllowedLocally', 405)

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
        exception_tuple = LambdaErrorResponses.ResourceNotFoundException

        return BaseLocalService.service_response(
            LambdaErrorResponses._construct_error_response_body(
                LambdaErrorResponses.USER_ERROR,
                "Function not found: arn:aws:lambda:us-west-2:012345678901:function:{}".format(function_name)
            ),
            LambdaErrorResponses._construct_headers(exception_tuple[0]),
            exception_tuple[1]
        )

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
        exception_tuple = LambdaErrorResponses.InvalidRequestContentException

        return BaseLocalService.service_response(
            LambdaErrorResponses._construct_error_response_body(LambdaErrorResponses.USER_ERROR, message),
            LambdaErrorResponses._construct_headers(exception_tuple[0]),
            exception_tuple[1]
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
        exception_tuple = LambdaErrorResponses.UnsupportedMediaTypeException

        return BaseLocalService.service_response(
            LambdaErrorResponses._construct_error_response_body(LambdaErrorResponses.USER_ERROR,
                                                                "Unsupported content type: {}".format(content_type)),
            LambdaErrorResponses._construct_headers(exception_tuple[0]),
            exception_tuple[1]
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
        exception_tuple = LambdaErrorResponses.ServiceException

        return BaseLocalService.service_response(
            LambdaErrorResponses._construct_error_response_body(LambdaErrorResponses.SERVICE_ERROR, "ServiceException"),
            LambdaErrorResponses._construct_headers(exception_tuple[0]),
            exception_tuple[1]
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
        exception_tuple = LambdaErrorResponses.NotImplementedException

        return BaseLocalService.service_response(
            LambdaErrorResponses._construct_error_response_body(LambdaErrorResponses.LOCAL_SERVICE_ERROR, message),
            LambdaErrorResponses._construct_headers(exception_tuple[0]),
            exception_tuple[1]
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
        exception_tuple = LambdaErrorResponses.PathNotFoundException

        return BaseLocalService.service_response(
            LambdaErrorResponses._construct_error_response_body(
                LambdaErrorResponses.LOCAL_SERVICE_ERROR, "PathNotFoundException"),
            LambdaErrorResponses._construct_headers(exception_tuple[0]),
            exception_tuple[1]
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
        exception_tuple = LambdaErrorResponses.MethodNotAllowedException

        return BaseLocalService.service_response(
            LambdaErrorResponses._construct_error_response_body(LambdaErrorResponses.LOCAL_SERVICE_ERROR,
                                                                "MethodNotAllowedException"),
            LambdaErrorResponses._construct_headers(exception_tuple[0]),
            exception_tuple[1]
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
        # OrderedDict is used to make testing in Py2 and Py3 consistent
        return json.dumps(OrderedDict([("Type", error_type), ("Message", error_message)]))

    @staticmethod
    def _construct_headers(error_type):
        """
        Constructs Headers for the Local Lambda Error Response

        Parameters
        ----------
        error_type str
            Error type that occurred to be put into the 'x-amzn-errortype' header

        Returns
        -------
        dict
            Dict representing the Lambda Error Response Headers
        """
        return {'x-amzn-errortype': error_type,
                'Content-Type': 'application/json'}
