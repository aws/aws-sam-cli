"""
A provider class that can parse and return Lambda Functions from a variety of sources. A SAM template is one such
source
"""

from collections import namedtuple

# Named Tuple to representing the properties of a Lambda Function
Function = namedtuple("Function", [
    # Function name or logical ID
    "name",

    # Runtime/language
    "runtime",

    # Memory in MBs
    "memory",

    # Function Timeout in seconds
    "timeout",

    # Name of the handler
    "handler",

    # Path to the code. This could be a S3 URI or local path or a dictionary of S3 Bucket, Key, Version
    "codeuri",

    # Environment variables. This is a dictionary with one key called Variables inside it. This contains the definition
    # of environment variables
    "environment",

    # Lambda Execution IAM Role ARN. In the future, this can be used by Local Lambda runtime to assume the IAM role
    # to get credentials to run the container with. This gives a much higher fidelity simulation of cloud Lambda.
    "rolearn"
])


class FunctionProvider(object):
    """
    Abstract base class of the function provider.
    """

    def get(self, name):
        """
        Given name of the function, this method must return the Function object

        :param string name: Name of the function
        :return Function: namedtuple containing the Function information
        """
        raise NotImplementedError("not implemented")

    def get_all(self):
        """
        Yields all the Lambda functions available in the provider.

        :yields Function: namedtuple containing the function information
        """
        raise NotImplementedError("not implemented")


_ApiTuple = namedtuple("Api", [

    # String. Path that this API serves. Ex: /foo, /bar/baz
    "path",

    # String. HTTP Method this API responds with
    "method",

    # String. Name of the Function this API connects to
    "function_name",

    # Optional Dictionary containing CORS configuration on this path+method
    # If this configuration is set, then API server will automatically respond to OPTIONS HTTP method on this path and
    # respond with appropriate CORS headers based on configuration.
    "cors",

    # List(Str). List of the binary media types the API
    "binary_media_types"
])
_ApiTuple.__new__.__defaults__ = (None,  # Cors is optional and defaults to None
                                  []     # binary_media_types is optional and defaults to empty
                                  )


class Api(_ApiTuple):
    def __hash__(self):
        # Other properties are not a part of the hash
        return hash(self.path) * hash(self.method) * hash(self.function_name)


Cors = namedtuple("Cors", ["AllowOrigin", "AllowMethods", "AllowHeaders"])


class ApiProvider(object):
    """
    Abstract base class to return APIs and the functions they route to
    """

    def get_all(self):
        """
        Yields all the APIs available.

        :yields Api: namedtuple containing the API information
        """
        raise NotImplementedError("not implemented")
