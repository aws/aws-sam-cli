"""
Class to store the API configurations in the SAM Template. This class helps store both implicit and explicit
routes in a standardized format
"""

import logging
from collections import defaultdict

from samcli.local.apigw.local_apigw_service import Route
from samcli.lib.providers.provider import Api

LOG = logging.getLogger(__name__)


class ApiCollector:
    def __init__(self):
        # Route properties stored per resource.
        self._route_per_resource = defaultdict(list)

        # processed values to be set before creating the api
        self._routes = []
        self.binary_media_types_set = set()
        self.stage_name = None
        self.stage_variables = None
        self.cors = None

    def __iter__(self):
        """
        Iterator to iterate through all the routes stored in the collector. In each iteration, this yields the
        LogicalId of the route resource and a list of routes available in this resource.
        Yields
        -------
        str
            LogicalID of the AWS::Serverless::Api or AWS::ApiGateway::RestApi resource
        list samcli.commands.local.lib.provider.Api
            List of the API available in this resource along with additional configuration like binary media types.
        """

        for logical_id, _ in self._route_per_resource.items():
            yield logical_id, self._get_routes(logical_id)

    def add_routes(self, logical_id, routes):
        """
        Stores the given routes tagged under the given logicalId
        Parameters
        ----------
        logical_id : str
            LogicalId of the AWS::Serverless::Api or AWS::ApiGateway::RestApi resource
        routes : list of samcli.commands.local.agiw.local_apigw_service.Route
            List of routes available in this resource
        """
        self._get_routes(logical_id).extend(routes)

    def _get_routes(self, logical_id):
        """
        Returns the properties of resource with given logical ID. If a resource is not found, then it returns an
        empty data.
        Parameters
        ----------
        logical_id : str
            Logical ID of the resource
        Returns
        -------
        samcli.commands.local.lib.Routes
            Properties object for this resource.
        """

        return self._route_per_resource[logical_id]

    @property
    def routes(self):
        return self._routes if self._routes else self.all_routes()

    @routes.setter
    def routes(self, routes):
        self._routes = routes

    def all_routes(self):
        """
        Gets all the routes within the _route_per_resource

        Return
        -------
        All the routes within the _route_per_resource
        """
        routes = []
        for logical_id in self._route_per_resource.keys():
            routes.extend(self._get_routes(logical_id))
        return routes

    def get_api(self):
        """
        Creates the api using the parts from the ApiCollector. The routes are also deduped so that there is no
        duplicate routes with the same function name, path, but different method.

        The normalised_routes are the routes that have been processed. By default, this will get all the routes.
        However, it can be changed to override the default value of normalised routes such as in SamApiProvider

        Return
        -------
        An Api object with all the properties
        """
        api = Api()
        routes = self.dedupe_function_routes(self.routes)
        routes = self.normalize_cors_methods(routes, self.cors)
        api.routes = routes
        api.binary_media_types_set = self.binary_media_types_set
        api.stage_name = self.stage_name
        api.stage_variables = self.stage_variables
        api.cors = self.cors
        return api

    @staticmethod
    def normalize_cors_methods(routes, cors):
        """
        Adds OPTIONS method to all the route methods if cors exists

        Parameters
        -----------
        routes: list(samcli.local.apigw.local_apigw_service.Route)
            List of Routes

        cors: samcli.commands.local.lib.provider.Cors
            the cors object for the api

        Return
        -------
        A list of routes without duplicate routes with the same function_name and method
        """

        def add_options_to_route(route):
            if "OPTIONS" not in route.methods:
                route.methods.append("OPTIONS")
            return route

        return routes if not cors else [add_options_to_route(route) for route in routes]

    @staticmethod
    def dedupe_function_routes(routes):
        """
         Remove duplicate routes that have the same function_name and method

         route: list(Route)
             List of Routes

        Return
        -------
        A list of routes without duplicate routes with the same function_name and method
        """
        grouped_routes = {}

        for route in routes:
            key = "{}-{}".format(route.function_name, route.path)
            config = grouped_routes.get(key, None)
            methods = route.methods
            if config:
                methods += config.methods
            sorted_methods = sorted(methods)
            grouped_routes[key] = Route(
                function_name=route.function_name,
                path=route.path,
                methods=sorted_methods,
                event_type=route.event_type,
                payload_format_version=route.payload_format_version,
            )
        return list(grouped_routes.values())

    def add_binary_media_types(self, logical_id, binary_media_types):
        """
        Stores the binary media type configuration for the API with given logical ID
        Parameters
        ----------

        logical_id : str
            LogicalId of the AWS::Serverless::Api resource

        api: samcli.commands.local.lib.provider.Api
            Instance of the Api which will save all the api configurations

        binary_media_types : list of str
            List of binary media types supported by this resource
        """

        binary_media_types = binary_media_types or []
        for value in binary_media_types:
            normalized_value = self.normalize_binary_media_type(value)

            # If the value is not supported, then just skip it.
            if normalized_value:
                self.binary_media_types_set.add(normalized_value)
            else:
                LOG.debug("Unsupported data type of binary media type value of resource '%s'", logical_id)

    @staticmethod
    def normalize_binary_media_type(value):
        """
        Converts binary media types values to the canonical format. Ex: image~1gif -> image/gif. If the value is not
        a string, then this method just returns None
        Parameters
        ----------
        value : str
            Value to be normalized
        Returns
        -------
        str or None
            Normalized value. If the input was not a string, then None is returned
        """

        if not isinstance(value, str):
            # It is possible that user specified a dict value for one of the binary media types. We just skip them
            return None

        return value.replace("~1", "/")
