"""
A provider class that can parse and return Lambda Functions from a variety of sources. A SAM template is one such
source
"""
import hashlib
import logging
from collections import namedtuple

from samcli.commands.local.cli_common.user_exceptions import InvalidLayerVersionArn, UnsupportedIntrinsic

LOG = logging.getLogger(__name__)

# Named Tuple to representing the properties of a Lambda Function
Function = namedtuple(
    "Function",
    [
        # Function name or logical ID
        "name",
        # Function name (used in place of logical ID)
        "functionname",
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
        "rolearn",
        # List of Layers
        "layers",
        # Event
        "events",
        # Metadata
        "metadata",
    ],
)


class ResourcesToBuildCollector:
    def __init__(self):
        self.result = {"Function": [], "Layer": []}

    def add_function(self, function):
        self.result.get("Function").append(function)

    def add_functions(self, functions):
        self.result.get("Function").extend(functions)

    def add_layer(self, layer):
        self.result.get("Layer").append(layer)

    def add_layers(self, layers):
        self.result.get("Layer").extend(layers)

    @property
    def functions(self):
        return self.result.get("Function")

    @property
    def layers(self):
        return self.result.get("Layer")

    def __eq__(self, other):
        if isinstance(other, type(self)):
            return self.__dict__ == other.__dict__

        return False


class LayerVersion:
    """
    Represents the LayerVersion Resource for AWS Lambda
    """

    LAYER_NAME_DELIMETER = "-"

    def __init__(self, arn, codeuri, compatible_runtimes=None, metadata=None):
        """
        Parameters
        ----------
        name str
            Name of the layer, this can be the ARN or Logical Id in the template
        codeuri str
            CodeURI of the layer. This should contain the path to the layer code
        """
        if compatible_runtimes is None:
            compatible_runtimes = []
        if metadata is None:
            metadata = {}
        if not isinstance(arn, str):
            raise UnsupportedIntrinsic("{} is an Unsupported Intrinsic".format(arn))

        self._arn = arn
        self._codeuri = codeuri
        self.is_defined_within_template = bool(codeuri)
        self._name = LayerVersion._compute_layer_name(self.is_defined_within_template, arn)
        self._version = LayerVersion._compute_layer_version(self.is_defined_within_template, arn)
        self._build_method = metadata.get("BuildMethod", None)
        self._compatible_runtimes = compatible_runtimes

    @staticmethod
    def _compute_layer_version(is_defined_within_template, arn):
        """
        Parses out the Layer version from the arn

        Parameters
        ----------
        is_defined_within_template bool
            True if the resource is a Ref to a resource otherwise False
        arn str
            ARN of the Resource

        Returns
        -------
        int
            The Version of the LayerVersion

        """

        if is_defined_within_template:
            return None

        try:
            _, layer_version = arn.rsplit(":", 1)
            layer_version = int(layer_version)
        except ValueError as ex:
            raise InvalidLayerVersionArn(arn + " is an Invalid Layer Arn.") from ex

        return layer_version

    @staticmethod
    def _compute_layer_name(is_defined_within_template, arn):
        """
        Computes a unique name based on the LayerVersion Arn

        Format:
        <Name of the LayerVersion>-<Version of the LayerVersion>-<sha256 of the arn>

        Parameters
        ----------
        is_defined_within_template bool
            True if the resource is a Ref to a resource otherwise False
        arn str
            ARN of the Resource

        Returns
        -------
        str
            A unique name that represents the LayerVersion
        """

        # If the Layer is defined in the template, the arn will represent the LogicalId of the LayerVersion Resource,
        # which does not require creating a name based on the arn.
        if is_defined_within_template:
            return arn

        try:
            _, layer_name, layer_version = arn.rsplit(":", 2)
        except ValueError as ex:
            raise InvalidLayerVersionArn(arn + " is an Invalid Layer Arn.") from ex

        return LayerVersion.LAYER_NAME_DELIMETER.join(
            [layer_name, layer_version, hashlib.sha256(arn.encode("utf-8")).hexdigest()[0:10]]
        )

    @property
    def arn(self):
        return self._arn

    @property
    def name(self):
        """
        A unique name from the arn or logical id of the Layer

        A LayerVersion Arn example:
        arn:aws:lambda:region:account-id:layer:layer-name:version

        Returns
        -------
        str
            A name of the Layer that is used on the system to uniquely identify the layer
        """
        return self._name

    @property
    def codeuri(self):
        return self._codeuri

    @property
    def version(self):
        return self._version

    @property
    def layer_arn(self):
        layer_arn, _ = self.arn.rsplit(":", 1)
        return layer_arn

    @codeuri.setter
    def codeuri(self, codeuri):
        self._codeuri = codeuri

    @property
    def build_method(self):
        return self._build_method

    @property
    def compatible_runtimes(self):
        return self._compatible_runtimes

    def __eq__(self, other):
        if isinstance(other, type(self)):
            return self.__dict__ == other.__dict__
        return False


class Api:
    def __init__(self, routes=None):
        if routes is None:
            routes = []
        self.routes = routes

        # Optional Dictionary containing CORS configuration on this path+method If this configuration is set,
        # then API server will automatically respond to OPTIONS HTTP method on this path and respond with appropriate
        # CORS headers based on configuration.

        self.cors = None
        # If this configuration is set, then API server will automatically respond to OPTIONS HTTP method on this
        # path and

        self.binary_media_types_set = set()

        self.stage_name = None
        self.stage_variables = None

    def __hash__(self):
        # Other properties are not a part of the hash
        return hash(self.routes) * hash(self.cors) * hash(self.binary_media_types_set)

    @property
    def binary_media_types(self):
        return list(self.binary_media_types_set)


_CorsTuple = namedtuple("Cors", ["allow_origin", "allow_methods", "allow_headers", "max_age"])

_CorsTuple.__new__.__defaults__ = (
    None,  # Allow Origin defaults to None
    None,  # Allow Methods is optional and defaults to empty
    None,  # Allow Headers is optional and defaults to empty
    None,  # MaxAge is optional and defaults to empty
)


class Cors(_CorsTuple):
    @staticmethod
    def cors_to_headers(cors):
        """
        Convert CORS object to headers dictionary
        Parameters
        ----------
        cors list(samcli.commands.local.lib.provider.Cors)
            CORS configuration objcet
        Returns
        -------
            Dictionary with CORS headers
        """
        if not cors:
            return {}
        headers = {
            "Access-Control-Allow-Origin": cors.allow_origin,
            "Access-Control-Allow-Methods": cors.allow_methods,
            "Access-Control-Allow-Headers": cors.allow_headers,
            "Access-Control-Max-Age": cors.max_age,
        }
        # Filters out items in the headers dictionary that isn't empty.
        # This is required because the flask Headers dict will send an invalid 'None' string
        return {h_key: h_value for h_key, h_value in headers.items() if h_value is not None}


class AbstractApiProvider:
    """
    Abstract base class to return APIs and the functions they route to
    """

    def get_all(self):
        """
        Yields all the APIs available.

        :yields Api: namedtuple containing the API information
        """
        raise NotImplementedError("not implemented")
