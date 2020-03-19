"""Base class for all Services that interact with Local Lambda"""

import json
import logging
import os

from flask import Response

LOG = logging.getLogger(__name__)


class BaseLocalService:
    def __init__(self, is_debugging, port, host):
        """
        Creates a BaseLocalService class

        Parameters
        ----------
        is_debugging bool
            Flag to run in debug mode or not
        port int
            Optional. port for the service to start listening on Defaults to 3000
        host str
            Optional. host to start the service on Defaults to '127.0.0.1
        """
        self.is_debugging = is_debugging
        self.port = port
        self.host = host
        self._app = None

    def create(self):
        """
        Creates a Flask Application that can be started.
        """
        raise NotImplementedError("Required method to implement")

    def run(self):
        """
        This starts up the (threaded) Local Server.
        Note: This is a **blocking call**

        Raises
        ------
        RuntimeError
            if the service was not created
        """
        if not self._app:
            raise RuntimeError("The application must be created before running")

        # Flask can operate as a single threaded server (which is default) and a multi-threaded server which is
        # more for development. When the Lambda container is going to be debugged, then it does not make sense
        # to turn on multi-threading because customers can realistically attach only one container at a time to
        # the debugger. Keeping this single threaded also enables the Lambda Runner to handle Ctrl+C in order to
        # kill the container gracefully (Ctrl+C can be handled only by the main thread)
        multi_threaded = not self.is_debugging

        LOG.debug("Localhost server is starting up. Multi-threading = %s", multi_threaded)

        # This environ signifies we are running a main function for Flask. This is true, since we are using it within
        # our cli and not on a production server.
        os.environ["WERKZEUG_RUN_MAIN"] = "true"

        self._app.run(threaded=multi_threaded, host=self.host, port=self.port)

    @staticmethod
    def service_response(body, headers, status_code):
        """
        Constructs a Flask Response from the body, headers, and status_code.

        :param str body: Response body as a string
        :param werkzeug.datastructures.Headers headers: headers for the response
        :param int status_code: status_code for response
        :return: Flask Response
        """
        response = Response(body)
        response.headers = headers
        response.status_code = status_code
        return response


class LambdaOutputParser:
    @staticmethod
    def get_lambda_output(stdout_stream):
        """
        This method will extract read the given stream and return the response from Lambda function separated out
        from any log statements it might have outputted. Logs end up in the stdout stream if the Lambda function
        wrote directly to stdout using System.out.println or equivalents.

        Parameters
        ----------
        stdout_stream : io.BaseIO
            Stream to fetch data from

        Returns
        -------
        str
            String data containing response from Lambda function
        str
            String data containng logs statements, if any.
        bool
            If the response is an error/exception from the container
        """
        # We only want the last line of stdout, because it's possible that
        # the function may have written directly to stdout using
        # System.out.println or similar, before docker-lambda output the result
        stdout_data = stdout_stream.getvalue().rstrip(b"\n")

        # Usually the output is just one line and contains response as JSON string, but if the Lambda function
        # wrote anything directly to stdout, there will be additional lines. So just extract the last line as
        # response and everything else as log output.
        lambda_response = stdout_data
        lambda_logs = None

        last_line_position = stdout_data.rfind(b"\n")
        if last_line_position >= 0:
            # So there are multiple lines. Separate them out.
            # Everything but the last line are logs
            lambda_logs = stdout_data[:last_line_position]
            # Last line is Lambda response. Make sure to strip() so we get rid of extra whitespaces & newlines around
            lambda_response = stdout_data[last_line_position:].strip()

        lambda_response = lambda_response.decode("utf-8")

        # When the Lambda Function returns an Error/Exception, the output is added to the stdout of the container. From
        # our perspective, the container returned some value, which is not always true. Since the output is the only
        # information we have, we need to inspect this to understand if the container returned a some data or raised an
        # error
        is_lambda_user_error_response = LambdaOutputParser.is_lambda_error_response(lambda_response)

        return lambda_response, lambda_logs, is_lambda_user_error_response

    @staticmethod
    def is_lambda_error_response(lambda_response):
        """
        Check to see if the output from the container is in the form of an Error/Exception from the Lambda invoke

        Parameters
        ----------
        lambda_response str
            The response the container returned

        Returns
        -------
        bool
            True if the output matches the Error/Exception Dictionary otherwise False
        """
        is_lambda_user_error_response = False
        try:
            lambda_response_dict = json.loads(lambda_response)

            # This is a best effort attempt to determine if the output (lambda_response) from the container was an
            # Error/Exception that was raised/returned/thrown from the container. To ensure minimal false positives in
            # this checking, we check for all the keys that can occur in Lambda raised/thrown/returned an
            # Error/Exception. This still risks false positives when the data returned matches exactly a dictionary with
            # the keys 'errorMessage', 'errorType', 'stackTrace' and 'cause'.
            # This also accounts for a situation where there are three keys returned, two of which are
            # 'errorMessage' and 'errorType', for languages with different error signatures
            if (
                isinstance(lambda_response_dict, dict)
                and len(lambda_response_dict.keys() & {"errorMessage", "errorType"}) == 2
                and (
                    (
                        len(lambda_response_dict.keys() & {"errorMessage", "errorType", "stackTrace", "cause"})
                        == len(lambda_response_dict)
                    )
                    or (len(lambda_response_dict) == 3)
                )
            ):
                is_lambda_user_error_response = True
        except ValueError:
            # If you can't serialize the output into a dict, then do nothing
            pass
        return is_lambda_user_error_response
