"""
Route definition for local start-api
"""
from typing import List, Optional

from samcli.local.apigw.authorizers.authorizer import Authorizer


class Route:
    API = "Api"
    HTTP = "HttpApi"
    ANY_HTTP_METHODS = ["GET", "DELETE", "PUT", "POST", "HEAD", "OPTIONS", "PATCH"]

    def __init__(
        self,
        function_name: Optional[str],
        path: str,
        methods: List[str],
        event_type: str = API,
        payload_format_version: Optional[str] = None,
        is_default_route: bool = False,
        operation_name=None,
        stack_path: str = "",
        authorizer_name: Optional[str] = None,
        authorizer_object: Optional[Authorizer] = None,
        use_default_authorizer: bool = True,
    ):
        """
        Creates an ApiGatewayRoute

        :param list(str) methods: http method
        :param function_name: Name of the Lambda function this API is connected to
        :param str path: Path off the base url
        :param str event_type: Type of the event. "Api" or "HttpApi"
        :param str payload_format_version: version of payload format
        :param bool is_default_route: determines if the default route or not
        :param string operation_name: Swagger operationId for the route
        :param str stack_path: path of the stack the route is located
        :param str authorizer_name: the authorizer this route is using, if any
        :param Authorizer authorizer_object: the authorizer object this route is using, if any
        :param bool use_default_authorizer: whether or not to use a default authorizer (if defined)
        """
        self.methods = self.normalize_method(methods)
        self.function_name = function_name
        self.path = path
        self.event_type = event_type
        self.payload_format_version = payload_format_version
        self.is_default_route = is_default_route
        self.operation_name = operation_name
        self.stack_path = stack_path
        self.authorizer_name = authorizer_name
        self.authorizer_object = authorizer_object
        self.use_default_authorizer = use_default_authorizer

    def __eq__(self, other):
        return (
            isinstance(other, Route)
            and sorted(self.methods) == sorted(other.methods)
            and self.function_name == other.function_name
            and self.path == other.path
            and self.operation_name == other.operation_name
            and self.stack_path == other.stack_path
            and self.authorizer_name == other.authorizer_name
            and self.authorizer_object == other.authorizer_object
            and self.use_default_authorizer == other.use_default_authorizer
        )

    def __hash__(self):
        route_hash = hash(f"{self.stack_path}-{self.function_name}-{self.path}")
        for method in sorted(self.methods):
            route_hash *= hash(method)
        return route_hash

    def normalize_method(self, methods):
        """
        Normalizes Http Methods. Api Gateway allows a Http Methods of ANY. This is a special verb to denote all
        supported Http Methods on Api Gateway.

        :param list methods: Http methods
        :return list: Either the input http_method or one of the _ANY_HTTP_METHODS (normalized Http Methods)
        """
        methods = [method.upper() for method in methods]
        if "ANY" in methods:
            return self.ANY_HTTP_METHODS
        return methods
