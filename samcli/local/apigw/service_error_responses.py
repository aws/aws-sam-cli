"""Class container to hold common Service Responses"""

from flask import jsonify, make_response


class ServiceErrorResponses(object):

    _NO_LAMBDA_INTEGRATION = {"message": "No function defined for resource method"}
    _MISSING_AUTHENTICATION = {"message": "Missing Authentication Token"}
    _LAMBDA_FAILURE = {"message": "Internal server error"}

    HTTP_STATUS_CODE_502 = 502
    HTTP_STATUS_CODE_403 = 403

    @staticmethod
    def lambda_failure_response(*args):
        """
        Helper function to create a Lambda Failure Response

        :return: A Flask Response
        """
        response_data = jsonify(ServiceErrorResponses._LAMBDA_FAILURE)
        return make_response(response_data, ServiceErrorResponses.HTTP_STATUS_CODE_502)

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
