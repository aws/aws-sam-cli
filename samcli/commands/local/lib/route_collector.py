"""
Class to store the Route list in the SAM Template. This class helps store both implicit and explicit
routes in a standardized format
"""

import logging
from collections import defaultdict

LOG = logging.getLogger(__name__)


class RouteCollector(object):

    def __init__(self):
        # Route properties stored per resource.
        self._route_per_resource = defaultdict(list)

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
