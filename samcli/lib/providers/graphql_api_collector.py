"""
Class to store the API configurations in the SAM Template. This class helps store both implicit and explicit
routes in a standardized format
"""

import logging
from collections import defaultdict

from samcli.local.apigw.local_apigw_service import Route
from samcli.lib.providers.provider import GraphQLApi

LOG = logging.getLogger(__name__)


class GraphQLApiCollector:
    def __init__(self):
        self._resolver_to_data_source = {
            'Query': {},
            'Mutation': {}
        }
        self._data_source_to_function = {}
        self._functions = []
        self._schema_path = None

    def add_resolver(self, resolver_type, field_name, data_source_logical_id):
        if resolver_type != "Query" and resolver_type != "Mutation":
            LOG.info("Tried to register a resolver of type %s, but this type is not supported. Resolver will be ignored.", resolver_type)

        self._resolver_to_data_source[resolver_type][field_name] = data_source_logical_id

    def add_data_source(self, data_source_logical_id, function_logical_id):
        self._data_source_to_function[data_source_logical_id] = function_logical_id

    def add_function(self, logical_id):
        self._functions.append(logical_id)

    def add_schema(self, schema_path):
        if self._schema_path is not None:
            raise NotImplementedError("Multiple schema's per template file is not supported")
        self._schema_path = schema_path

    def get_api(self):
        resolvers = {
            'Query': {},
            'Mutation': {}
        }
        for resolver_type, resolver_set in self._resolver_to_data_source.items():
            for field_name, data_source_logical_id in resolver_set.items():
                if data_source_logical_id not in self._data_source_to_function:
                    LOG.info("Missing data source %s for resolver %s / %s", data_source_logical_id, resolver_type, field_name)
                elif self._data_source_to_function[data_source_logical_id] not in self._functions:
                    LOG.info(
                        "Missing function %s for resolver %s / %s, functions need to be present in the same template", 
                        self._data_source_to_function[data_source_logical_id], resolver_type, field_name
                    )
                else:
                    function_logical_id = self._data_source_to_function[data_source_logical_id]
                    resolvers[resolver_type][field_name] = function_logical_id
        
        if self._schema_path is None:
            raise AttributeError("A schema is missing from the template, cannot create GraphQL API")
        
        api = GraphQLApi()
        api.schema_path = self._schema_path
        api.resolvers = resolvers
        return api