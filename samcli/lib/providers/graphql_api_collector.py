"""
Class to store the API configurations in the SAM Template. This class helps store both implicit and explicit
routes in a standardized format
"""

import logging

from samcli.local.appsync.local_appsync_service import Resolver
from samcli.lib.providers.provider import GraphQLApi

LOG = logging.getLogger(__name__)


class GraphQLApiCollector:
    def __init__(self):
        self._resolvers = []
        self._data_source_to_function = {}
        self._functions = []
        self._schema_path = None

    def add_resolver(self, object_type, field_name, data_source_logical_id):
        self._resolvers.append(
            {
                "object_type": object_type,
                "field_name": field_name,
                "data_source_logical_id": data_source_logical_id,
            }
        )

    def add_data_source(self, data_source_logical_id, function_logical_id):
        self._data_source_to_function[data_source_logical_id] = function_logical_id

    def add_function(self, logical_id):
        self._functions.append(logical_id)

    def add_schema(self, schema_path):
        if self._schema_path is not None:
            raise NotImplementedError("Multiple schema's per template file is not supported")
        self._schema_path = schema_path

    def get_api(self):
        resolvers = []

        for resolver in self._resolvers:
            data_source_logical_id = resolver.get("data_source_logical_id")
            if data_source_logical_id not in self._data_source_to_function:
                LOG.info("Missing data source %s for resolver %s", data_source_logical_id, resolver)
            elif self._data_source_to_function[data_source_logical_id] not in self._functions:
                LOG.info(
                    "Missing function %s for resolver %s, functions need to be present in the same template",
                    self._data_source_to_function[data_source_logical_id],
                    resolver,
                )
            else:
                function_logical_id = self._data_source_to_function[data_source_logical_id]

                resolvers.append(
                    Resolver(
                        function_logical_id,
                        resolver.get("object_type"),
                        resolver.get("field_name"),
                    )
                )

        api = GraphQLApi()
        api.schema_path = self._schema_path
        api.resolvers = resolvers
        return api
