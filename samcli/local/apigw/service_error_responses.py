"""Class container to hold common Service Responses"""

import logging

from flask import Response, jsonify, make_response

LOG = logging.getLogger(__name__)


class ServiceErrorResponses:
    _NO_LAMBDA_INTEGRATION = {"message": "No function defined for resource method"}
    _MISSING_AUTHENTICATION = {"message": "Missing Authentication Token"}
    _LAMBDA_FAILURE = {"message": "Internal server error"}
    _MISSING_LAMBDA_AUTH_IDENTITY_SOURCES = {"message": "Unauthorized"}
    _LAMBDA_AUTHORIZER_NOT_AUTHORIZED = {"message": "User is not authorized to access this resource"}

    HTTP_STATUS_CODE_500 = 500
    HTTP_STATUS_CODE_501 = 501
    HTTP_STATUS_CODE_502 = 502
    HTTP_STATUS_CODE_403 = 403
    HTTP_STATUS_CODE_401 = 401

    @staticmethod
    def lambda_authorizer_unauthorized() -> Response:
        """
        Constructs a Flask response for when a route invokes a Lambda Authorizer, but
        is the identity sources provided are not authorized for that method

        Returns
        -------
        Response
            A Flask Response object
        """
        response_data = jsonify(ServiceErrorResponses._LAMBDA_AUTHORIZER_NOT_AUTHORIZED)
        return make_response(response_data, ServiceErrorResponses.HTTP_STATUS_CODE_403)

    @staticmethod
    def missing_lambda_auth_identity_sources() -> Response:
        """
        Constructs a Flask response for when a route contains a Lambda Authorizer
        but is missing the required identity services

        Returns
        -------
        Response
            A Flask Response object
        """
        response_data = jsonify(ServiceErrorResponses._MISSING_LAMBDA_AUTH_IDENTITY_SOURCES)
        return make_response(response_data, ServiceErrorResponses.HTTP_STATUS_CODE_401)

    @staticmethod
    def lambda_failure_response(*args):
        """
        Helper function to create a Lambda Failure Response

        :return: A Flask Response
        """
        LOG.debug("Lambda execution failed %s", args)
        response_data = jsonify(ServiceErrorResponses._LAMBDA_FAILURE)
        return make_response(response_data, ServiceErrorResponses.HTTP_STATUS_CODE_502)

    @staticmethod
    def lambda_body_failure_response(*args):
        """
        Helper function to create a Lambda Body Failure Response

        :return: A Flask Response
        """
        response_data = jsonify(ServiceErrorResponses._LAMBDA_FAILURE)
        return make_response(response_data, ServiceErrorResponses.HTTP_STATUS_CODE_500)

    @staticmethod
    def not_implemented_locally(message):
        """
        Constructs a Flask Response for for when a Lambda function functionality is
        not implemented

        :return: a Flask Response
        """
        exception_dict = {"message": message}
        response_data = jsonify(exception_dict)
        return make_response(response_data, ServiceErrorResponses.HTTP_STATUS_CODE_501)

    @staticmethod
    def lambda_not_found_response(*args):
        """
        Constructs a Flask Response for when a Lambda function is not found for an endpoint

        :return: a Flask Response
        """
        response_data = jsonify(ServiceErrorResponses._NO_LAMBDA_INTEGRATION)
        return make_response(response_data, ServiceErrorResponses.HTTP_STATUS_CODE_502)

    @staticmethod
    def route_not_found(*args):
        """
        Constructs a Flask Response for when a API Route (path+method) is not found. This is usually
        HTTP 404 but with API Gateway this is a HTTP 403 (https://forums.aws.amazon.com/thread.jspa?threadID=2166840)

        :return: a Flask Response
        """
        response_data = jsonify(ServiceErrorResponses._MISSING_AUTHENTICATION)
        return make_response(response_data, ServiceErrorResponses.HTTP_STATUS_CODE_403)

    @staticmethod
    def container_creation_failed(message):
        """
        Constuct a Flask Response for when container creation fails for a Lambda Function
        :return: a Flask Response
        """
        response_data = jsonify({"message": message})
        return make_response(response_data, ServiceErrorResponses.HTTP_STATUS_CODE_501)
