""" To isolate Schemas API calls """

import json
from json import JSONDecodeError

from botocore.exceptions import ClientError, EndpointConnectionError

from samcli.lib.schemas.schemas_directory_hierarchy_builder import sanitize_name, get_package_hierarchy
from samcli.lib.schemas.schemas_constants import DEFAULT_EVENT_SOURCE, DEFAULT_EVENT_DETAIL_TYPE
from samcli.commands.exceptions import SchemasApiException
from samcli.commands.local.cli_common.user_exceptions import ResourceNotFound, NotAvailableInRegion

SCHEMAS_NOT_AVAILABLE_IN_REGION_ERROR = (
    "EventBridge Schemas are not available in provided region. Please check AWS doc for Schemas supported regions."
)


class SchemasApiCaller:
    def __init__(self, schemas_client):
        self._schemas_client = schemas_client

    def list_registries(self, next_token=None, limit=10):
        """
        Calls schemas service to get list of schema registries.

        Parameters
        ----------
        next_token:
            Continuation token
        limit:
            Number of items tro fetch

        Returns
        -------
        List of registries available
        """
        if limit is None:
            limit = 10
        registries = []
        try:
            paginator = self._schemas_client.get_paginator("list_registries")
            page_iterator = paginator.paginate(
                PaginationConfig={"StartingToken": next_token, "MaxItems": limit, "PageSize": limit}
            )
            page = None
            for page in page_iterator:
                for registry in page["Registries"]:
                    registries.append(registry["RegistryName"])
            if not registries:
                raise ResourceNotFound("No Registries found. This should not be possible, please raise an issue.")
            next_token = page.get("NextToken", None)
            return {"registries": registries, "next_token": next_token}
        except EndpointConnectionError as ex:
            raise NotAvailableInRegion(SCHEMAS_NOT_AVAILABLE_IN_REGION_ERROR) from ex

    def list_schemas(self, registry_name, next_token=None, limit=10):
        """
        Calls schemas service to get list of schemas for given registry.

        Parameters
        ----------
        registry_name:
            Name of the registry
        next_token:
            Continuation token
        limit:
            Number of items to fetch

        Returns
        -------
        List of Schemas available for given registry
        """
        schemas = []
        try:
            paginator = self._schemas_client.get_paginator("list_schemas")
            page_iterator = paginator.paginate(
                RegistryName=registry_name,
                PaginationConfig={"StartingToken": next_token, "MaxItems": limit, "PageSize": limit},
            )
            page = None
            for page in page_iterator:
                for schema in page["Schemas"]:
                    schemas.append(schema["SchemaName"])
            if not schemas:
                raise ResourceNotFound("No Schemas found for registry %s" % registry_name)
            next_token = page.get("NextToken", None)
            return {"schemas": schemas, "next_token": next_token}
        except EndpointConnectionError as ex:
            raise NotAvailableInRegion(SCHEMAS_NOT_AVAILABLE_IN_REGION_ERROR) from ex

    def get_latest_schema_version(self, registry_name, schema_name):
        """
        Calls schemas service to get schema latest version.

        Parameters
        ----------
        registry_name:
            Registry name
        schema_name:
            Schema Name

        Returns
        -------
        Latest Schema version
        """
        versions = []
        next_token = None
        try:
            while True:
                paginator = self._schemas_client.get_paginator("list_schema_versions")
                page_iterator = paginator.paginate(
                    RegistryName=registry_name, SchemaName=schema_name, PaginationConfig={"StartingToken": next_token}
                )
                page = None
                for page in page_iterator:
                    for version in page["SchemaVersions"]:
                        versions.append(version["SchemaVersion"])

                next_token = page.get("NextToken")
                if next_token is None:
                    break
        except EndpointConnectionError as ex:
            raise NotAvailableInRegion(SCHEMAS_NOT_AVAILABLE_IN_REGION_ERROR) from ex
        versions.sort()
        return versions[-1]

    def get_schema_metadata(self, registry_name, schema_name):
        """
        Calls schemas service to get schema metadata.

        Parameters
        ----------
        registry_name:
            Registry Name
        schema_name:
            Schema Name

        Returns
        -------
        Schema metadata
        """
        try:
            describe_schema_response = self._schemas_client.describe_schema(
                RegistryName=registry_name, SchemaName=schema_name
            )
        except EndpointConnectionError as ex:
            raise NotAvailableInRegion(SCHEMAS_NOT_AVAILABLE_IN_REGION_ERROR) from ex
        try:
            content = json.loads(describe_schema_response["Content"])
            schemas = content["components"]["schemas"]
            # setting default values
            event_source = DEFAULT_EVENT_SOURCE
            event_source_detail_type = DEFAULT_EVENT_DETAIL_TYPE
            schema_root_name = sanitize_name(list(schemas.keys())[0])
            schemas_package_hierarchy = get_package_hierarchy(schema_name)
            if schemas.get("AWSEvent") is not None:
                aws_event = schemas.get("AWSEvent")
                if aws_event.get("x-amazon-events-source") is not None:
                    event_source = aws_event.get("x-amazon-events-source")
                if aws_event.get("x-amazon-events-detail-type") is not None:
                    event_source_detail_type = aws_event.get("x-amazon-events-detail-type")
                possible_root_schema_name = aws_event["properties"]["detail"]["$ref"]
                schema_root_name = sanitize_name(possible_root_schema_name[len("#/components/schemas/") :])
            return {
                "event_source": event_source,
                "event_source_detail_type": event_source_detail_type,
                "schema_root_name": schema_root_name,
                "schemas_package_hierarchy": schemas_package_hierarchy,
            }

        except JSONDecodeError as ex:
            raise SchemasApiException(
                "Parse error reading the content from Schemas response. This should not be possible, please raise an issue."
            ) from ex

    def download_source_code_binding(self, runtime, registry_name, schema_name, schema_version, download_location):
        """
        Calls schemas service to download code binding for given schema in download_location.

        Parameters
        ----------
        runtime:
            Code binding runtime e.g: Java, Python
        registry_name:
            Registry Name
        schema_name:
            Schema Name
        schema_version:
            Schema version for which code binding needs to be downloaded
        download_location:
            Location at which code binding should be downloaded
        """
        try:
            response = self._schemas_client.get_code_binding_source(
                Language=runtime, RegistryName=registry_name, SchemaName=schema_name, SchemaVersion=schema_version
            )
        except EndpointConnectionError as ex:
            raise NotAvailableInRegion(SCHEMAS_NOT_AVAILABLE_IN_REGION_ERROR) from ex

        for data in response["Body"]:
            download_location.write(data)

    def put_code_binding(self, runtime, registry_name, schema_name, schema_version):
        """
        Calls schemas service to generate code binding for given schema.

        Parameters
        ----------
        runtime:
            Code binding runtime e.g: Java, Python
        registry_name:
            Registry Name
        schema_name:
            Schema Name
        schema_version:
            Schema version for which code binding needs to be generated
        """
        try:
            self._schemas_client.put_code_binding(
                Language=runtime, RegistryName=registry_name, SchemaName=schema_name, SchemaVersion=schema_version
            )
        except EndpointConnectionError as ex:
            raise NotAvailableInRegion(
                "EventBridge Schemas are not available in provided region. "
                "Please check AWS doc for Schemas supported regions."
            ) from ex
        except ClientError as e:
            if e.response["Error"]["Code"] != "ConflictException":
                raise e

    def poll_for_code_binding_status(self, schemas_runtime, registry_name, schema_name, schema_version):
        """
        Calls schemas service and wait for code binding to be generated.

        Parameters
        ----------
        schemas_runtime:
            Code binding runtime e.g: Java, Python
        registry_name:
            Registry Name
        schema_name:
            Schema Name
        schema_version:
            Schema version
        """
        try:
            waiter = self._schemas_client.get_waiter("code_binding_exists")
            waiter.wait(
                Language=schemas_runtime,
                RegistryName=registry_name,
                SchemaName=schema_name,
                SchemaVersion=schema_version,
            )
        except EndpointConnectionError as ex:
            raise NotAvailableInRegion(SCHEMAS_NOT_AVAILABLE_IN_REGION_ERROR) from ex
