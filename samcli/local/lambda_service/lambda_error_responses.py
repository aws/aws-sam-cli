""" Common Lambda Error Response"""

import json

from flask import Response


class LambdaErrorResponses(object):

    # The content type of the Invoke request body is not JSON.
    UnsupportedMediaTypeException = ('UnsupportedMediaType', 415)

    # The AWS Lambda service encountered an internal error.
    ServiceException = ('Service', 500)

    # The resource (for example, a Lambda function or access policy statement) specified in the request does not exist.
    ResourceNotFoundException = ('ResourceNotFound', 404)

    # The request body could not be parsed as JSON.
    InvalidRequestContentException = ('InvalidRequestContent', 400)

    @staticmethod
    def resource_not_found(function_name):
        """

        Parameters
        ----------
        function_name

        Returns
        -------

        """
        return LambdaErrorResponses._service_response(json.dumps(
            {"Message": "Function not found: arn:aws:lambda:us-west-2:012345678901:function:{}".format(function_name),
             "Type": "User"}),
            {'x-amzn-errortype': LambdaErrorResponses.ResourceNotFoundException[0], 'Content-Type': 'application/json'},
            LambdaErrorResponses.ResourceNotFoundException[1])

    @staticmethod
    def invalid_request_content(message):
        return LambdaErrorResponses._service_response(json.dumps(
            {"Type": "User",
             "message": message}),
            {'x-amzn-errortype': 'InvalidRequestContentException', 'Content-Type': 'application/json'},
            400
        )

    @staticmethod
    def unsupported_media_type(content_type):
        return LambdaErrorResponses._service_response(json.dumps(
            {"Type": "User",
             "message": "Unsupported content type: {}".format(content_type)}),
            {'x-amzn-errortype': 'UnsupportedMediaType', 'Content-Type': 'application/json'},
            415
        )

    @staticmethod
    def generic_service_exception():
        return LambdaErrorResponses._service_response(json.dumps(
            {"Type": "Service",
             "message": "ServiceException"}),
            {'x-amzn-errortype': 'ServiceException', 'Content-Type': 'application/json'},
            500
        )

    @staticmethod
    def not_implemented_locally(message):
        return LambdaErrorResponses._service_response(json.dumps(
            {"Type": "LocalService",
             "message": message}),
            {'x-amzn-errortype': 'NotImplemented', 'Content-Type': 'application/json'},
            501
        )

    @staticmethod
    def _service_response(body, headers, status_code):
        """
        Constructs a Flask Response from the body, headers, and status_code.

        :param str body: Response body as a string
        :param dict headers: headers for the response
        :param int status_code: status_code for response
        :return: Flask Response
        """
        response = Response(body)
        response.headers = headers
        response.status_code = status_code
        return response
