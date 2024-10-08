"""
Supplies the environment variables necessary to set up Local Lambda runtime
"""

import sys
from enum import IntEnum


class Python(IntEnum):
    TWO = 2


class EnvironmentVariables:
    """
    Use this class to get the environment variables necessary to run the Lambda function. It returns the AWS specific
    variables (credentials, regions, etc) along with any environment variables configured on the function.

    Customers define the name of the environment variables along with default values, if any, when creating the
    function. In order to test the function with different scenarios, customers can override values for some of the
    variables. This class supports three mechanisms of providing values to environment variables.
    If a variable is given a value through all the three mechanisms, then the value from higher priority will be used:

    Priority (Highest to Lowest):
        - Override Values - User specified these
        - Shell Environment Values - Came from the shell environment
        - Default Values - Hard coded values

    If a variable does *not* get a value from either of the above mechanisms, it is given a value of "" (empty string).
    If the value of a variable is an intrinsic function dict/list, then it is given a value of "" (empty string).

    If real AWS Credentials were supplied, this class will expose them through appropriate environment variables.
    If not, this class will provide the following placeholder values to AWS Credentials:
        region = "us-east-1"
        key = "defaultkey"
        secret = "defaultsecret"
    """

    _BLANK_VALUE = ""
    _DEFAULT_AWS_CREDS = {"region": "us-east-1", "key": "defaultkey", "secret": "defaultsecret"}

    def __init__(
        self,
        function_name=None,
        function_memory=None,
        function_timeout=None,
        function_handler=None,
        function_logging_config=None,
        variables=None,
        shell_env_values=None,
        override_values=None,
        aws_creds=None,
    ):
        """
        Initializes this class. It takes in two sets of properties:
            a) (Required) Function information
            b) (Optional) Environment variable configured on the function

        :param str function_name: The name of the function
        :param integer function_memory: Memory size of the function in megabytes
        :param integer function_timeout: Function's timeout in seconds
        :param string function_handler: Handler of the function
        :param string function_logging_config: Logging Config for the function
        :param dict variables: Optional. Dict whose key is the environment variable names and value is the default
            values for the variable.
        :param dict shell_env_values: Optional. Dict containing values for the variables grabbed from the shell's
            environment.
        :param dict override_values: Optional. Dict containing values for the variables that will override the values
            from ``default_values`` and ``shell_env_values``.
        :param dict aws_creds: Optional. Dictionary containing AWS credentials passed to the Lambda runtime through
            environment variables. It should contain "key", "secret", "region" and optional "sessiontoken" keys
        """

        self._function = {
            "memory": function_memory,
            "timeout": function_timeout,
            "handler": function_handler,
            "name": function_name,
        }

        self.variables = variables or {}
        self.shell_env_values = shell_env_values or {}
        self.override_values = override_values or {}
        self.aws_creds = aws_creds or {}
        self.logging_config = function_logging_config or {}

    def resolve(self):
        """
        Resolves the values from different sources and returns a dict of environment variables to use when running
        the function locally.

        :return dict: Dict where key is the variable name and value is the value of the variable. Both key and values
            are strings
        """

        # AWS_* variables must always be passed to the function, but user has the choice to override them
        result = self._get_aws_variables()

        # Default value for the variable gets lowest priority
        for name, value in self.variables.items():
            override_value = value

            # Shell environment values, second priority
            if name in self.shell_env_values:
                override_value = self.shell_env_values[name]

            # Overridden values, highest priority
            if name in self.override_values:
                override_value = self.override_values[name]

            # Any value must be a string when passed to Lambda runtime.
            # Runtime expects a Map<String, String> for environment variables
            result[name] = self._stringify_value(override_value)

        return result

    def add_lambda_event_body(self, value):
        """
        Adds the value of AWS_LAMBDA_EVENT_BODY environment variable.
        """
        self.variables["AWS_LAMBDA_EVENT_BODY"] = value

    @property
    def timeout(self):
        return self._function["timeout"]

    @timeout.setter
    def timeout(self, value):
        self._function["timeout"] = value

    @property
    def memory(self):
        return self._function["memory"]

    @memory.setter
    def memory(self, value):
        self._function["memory"] = value

    @property
    def handler(self):
        return self._function["handler"]

    @handler.setter
    def handler(self, value):
        self._function["handler"] = value

    @property
    def name(self):
        return self._function["name"]

    @name.setter
    def name(self, value):
        self._function["name"] = value

    def _get_aws_variables(self):
        """
        Returns the AWS specific environment variables that should be available in the Lambda runtime.
        They are prefixed it "AWS_*".

        :return dict: Name and value of AWS environment variable
        """

        result = {
            # Variable that says this function is running in Local Lambda
            "AWS_SAM_LOCAL": "true",
            # Function configuration
            "AWS_LAMBDA_FUNCTION_MEMORY_SIZE": str(self.memory),
            "AWS_LAMBDA_FUNCTION_TIMEOUT": str(self.timeout),
            "AWS_LAMBDA_FUNCTION_HANDLER": self._function["handler"],
            "AWS_LAMBDA_FUNCTION_NAME": str(self.name),
            "AWS_LAMBDA_FUNCTION_VERSION": "$LATEST",
            "AWS_LAMBDA_LOG_GROUP_NAME": f"aws/lambda/{self.name}",
            "AWS_LAMBDA_LOG_STREAM_NAME": "$LATEST",
            # AWS Credentials - Use the input credentials or use the defaults
            "AWS_REGION": self.aws_creds.get("region", self._DEFAULT_AWS_CREDS["region"]),
            "AWS_DEFAULT_REGION": self.aws_creds.get("region", self._DEFAULT_AWS_CREDS["region"]),
            "AWS_ACCESS_KEY_ID": self.aws_creds.get("key", self._DEFAULT_AWS_CREDS["key"]),
            "AWS_SECRET_ACCESS_KEY": self.aws_creds.get("secret", self._DEFAULT_AWS_CREDS["secret"]),
            "AWS_ACCOUNT_ID": "123456789012",
            "AWS_LAMBDA_INITIALIZATION_TYPE": "on-demand",
        }

        # Session Token should be added **only** if the input creds have a token and the value is not empty.
        if self.aws_creds.get("sessiontoken"):
            result["AWS_SESSION_TOKEN"] = self.aws_creds.get("sessiontoken")

        # Add the ApplicationLogLevel as a env variable and also update the function's LogGroup name
        log_group = self.logging_config.get("LogGroup")
        if log_group:
            result["AWS_LAMBDA_LOG_GROUP_NAME"] = log_group

        log_format = self.logging_config.get("LogFormat")
        if log_format:
            result["AWS_LAMBDA_LOG_FORMAT"] = log_format
            if log_format == "JSON":
                result["AWS_LAMBDA_LOG_LEVEL"] = self.logging_config.get("ApplicationLogLevel", "INFO")

        return result

    def _stringify_value(self, value):
        """
        This method stringifies values of environment variables. If the value of the method is a list or dictionary,
        then this method will replace it with empty string. Values of environment variables in Lambda must be a string.
        List or dictionary usually means they are intrinsic functions which have not been resolved.

        :param value: Value to stringify
        :return string: Stringified value
        """

        # List/dict/None values are replaced with a blank
        if isinstance(value, (dict, list, tuple)) or value is None:
            result = self._BLANK_VALUE

        # str(True) will output "True". To maintain backwards compatibility we need to output "true" or "false"
        elif value is True:
            result = "true"
        elif value is False:  # pylint: disable=compare-to-zero
            result = "false"

        # value is a scalar type like int, str which can be stringified
        # do not stringify unicode in Py2, Py3 str supports unicode
        elif sys.version_info.major > Python.TWO:
            result = str(value)
        elif not isinstance(value, unicode):  # noqa: F821 pylint: disable=undefined-variable
            result = str(value)
        else:
            result = value

        return result

    def __eq__(self, other):
        if not isinstance(other, EnvironmentVariables):
            return False
        return self.resolve() == other.resolve()
