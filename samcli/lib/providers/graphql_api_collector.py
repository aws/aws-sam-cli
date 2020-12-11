"""
Class to store the API configurations in the SAM Template. This class helps store both implicit and explicit
routes in a standardized format
"""

import logging
from collections import defaultdict

from samcli.local.apigw.local_apigw_service import Route
from samcli.lib.providers.provider import Api

LOG = logging.getLogger(__name__)


class GraphQLApiCollector:
    def __init__(self):
        # Route properties stored per resource.
        self._resolvers = defaultdict(list)

    def add_resolver(self, resolver_type, field_name, function_resource_name):
        LOG.info("I will add some resolver later %s %s %s", resolver_type, field_name, function_resource_name)

    def add_data_source(self, data_source_logical_id, function_logical_id):
        LOG.info("Connecting %s to lambda %s", data_source_logical_id, function_logical_id)

    def add_function(self, logical_id):
        LOG.info("Adding function %s", logical_id)

    def get_api(self):
        raise NotImplementedError("not implemented")