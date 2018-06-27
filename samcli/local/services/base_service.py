from flask import Response


class BaseService(object):

    def __init__(self, lambda_runner, port=None, host=None, stderr=None):
        self.lambda_runner = lambda_runner
        self.port = port or self._DEFAULT_PORT
        self.host = host or self._DEFAULT_HOST
        self._app = None
        self.stderr = stderr

    @staticmethod
    def _get_lambda_output(stdout_stream):
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
        """
        # We only want the last line of stdout, because it's possible that
        # the function may have written directly to stdout using
        # System.out.println or similar, before docker-lambda output the result
        stdout_data = stdout_stream.getvalue().rstrip(b'\n')

        # Usually the output is just one line and contains response as JSON string, but if the Lambda function
        # wrote anything directly to stdout, there will be additional lines. So just extract the last line as
        # response and everything else as log output.
        lambda_response = stdout_data
        lambda_logs = None

        last_line_position = stdout_data.rfind(b'\n')
        if last_line_position > 0:
            # So there are multiple lines. Separate them out.
            # Everything but the last line are logs
            lambda_logs = stdout_data[:last_line_position]
            # Last line is Lambda response. Make sure to strip() so we get rid of extra whitespaces & newlines around
            lambda_response = stdout_data[last_line_position:].strip()

        return lambda_response, lambda_logs

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