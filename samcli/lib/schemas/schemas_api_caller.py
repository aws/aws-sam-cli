"""To isolate Schemas API calls"""

import json
import logging
from json import JSONDecodeError

from botocore.exceptions import ClientError, EndpointConnectionError

from samcli.commands.exceptions import SchemasApiException
from samcli.commands.local.cli_common.user_exceptions import (
    NotAvailableInRegion,
    ResourceNotFound,
)
from samcli.lib.schemas.schemas_constants import DEFAULT_EVENT_DETAIL_TYPE, DEFAULT_EVENT_SOURCE
from samcli.lib.schemas.schemas_directory_hierarchy_builder import get_package_hierarchy, sanitize_name

SCHEMAS_NOT_AVAILABLE_IN_REGION_ERROR = (
    "EventBridge Schemas are not available in provided region. Please check AWS doc for Schemas supported regions."
)

LOG = logging.getLogger(__name__)


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

    def list_schema_versions(self, registry_name, schema_name):
        """
        Calls schemas service to list all schema versions.

        Parameters
        ----------
        registry_name:
            Registry name
        schema_name:
            Schema Name

        Returns
        -------
        List of Schema versions
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
        versions.sort(key=int)
        return versions

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
        versions = self.list_schema_versions(registry_name, schema_name)
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
                "Parse error reading the content from Schemas response. "
                "This should not be possible, please raise an issue."
            ) from ex

    def download_source_code_binding(self, runtime, registry_name, schema_name, schema_version, download_location):
        """
        Calls schemas service to download code binding for given schema in download_location.

        Parameters
        ----------
        runtime:
            Code binding runtime e.g: Java, Python, Go
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
            Code binding runtime e.g: Java, Python, Go
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
            Code binding runtime e.g: Java, Python, Go
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

    def discover_schema(self, event_data: str, schema_type: str) -> str:
        """
        Returns a schema based on an event using the DiscoverSchema API

        Parameters
        ----------
        event_data:
            A JSON test event as a string
        schema_type:
            Type of the schema to generate ("OpenApi3" or "JSONSchemaDraft4")
        Returns
        -------
        Generated schema JSON as a string
        """
        try:
            LOG.debug("Discover schema from contents: '%s'.", event_data)
            schema = self._schemas_client.get_discovered_schema(Events=[event_data], Type=schema_type)

            return str(schema["Content"])
        except EndpointConnectionError as ex:
            LOG.error("Failure calling get_discovered_schema")
            raise NotAvailableInRegion(SCHEMAS_NOT_AVAILABLE_IN_REGION_ERROR) from ex

    def create_schema(self, schema: str, registry_name: str, schema_name: str, schema_type: str):
        """
        Creates a new schema in the specified registry

        Parameters
        ----------
        schema:
            Contents for the schema to be created
        registry_name:
            The registry the schema will be created in
        schema_name:
            The name for the new created schema
        schema_type:
            Type of the schema to generate ("OpenApi3" or "JSONSchemaDraft4")
        """
        try:
            LOG.debug("Creating schema %s on registry %s.", schema_name, registry_name)
            self._schemas_client.create_schema(
                Content=schema, RegistryName=registry_name, SchemaName=schema_name, Type=schema_type
            )
            return True
        except EndpointConnectionError as ex:
            LOG.error("Failure calling create_schema in registry %s for schema %s", registry_name, schema_name)
            raise NotAvailableInRegion(SCHEMAS_NOT_AVAILABLE_IN_REGION_ERROR) from ex

    def update_schema(self, schema: str, registry_name: str, schema_name: str, schema_type: str):
        """
        Updates an existing schema

        Parameters
        ----------
        schema:
            Contents for the updated schema
        registry_name:
            The registry of the schema that will be updated
        schema_name:
            The name of the schema to be updated
        schema_type:
            Type of the schema to generate ("OpenApi3" or "JSONSchemaDraft4")
        """
        try:
            LOG.debug("Updating schema %s on registry %s.", schema_name, registry_name)
            self._schemas_client.update_schema(
                Content=schema, RegistryName=registry_name, SchemaName=schema_name, Type=schema_type
            )
            return True
        except ClientError as ex:
            error_message: str = ex.response.get("Message", "")  # type: ignore
            if ex.response.get("Code") == "Conflict" and "No change since the previous" in error_message:
                # Nothing to update
                LOG.debug("No changes to the schema from the previous version")
                return True
            raise ex

        except EndpointConnectionError as ex:
            LOG.error("Failure calling update_schema in registry %s for schema %s", registry_name, schema_name)
            raise NotAvailableInRegion(SCHEMAS_NOT_AVAILABLE_IN_REGION_ERROR) from ex

    def get_schema(self, registry_name: str, schema_name: str) -> str:
        """
        Gets a schema from the registry

        Parameters
        ----------
        registry_name:
            The registry of the schema that will be updated
        schema_name:
            The name of the schema to be updated
        Returns
        -------
        A schema dict
        """
        try:
            LOG.debug("Describing schema %s on registry %s.", schema_name, registry_name)
            schema = self._schemas_client.describe_schema(RegistryName=registry_name, SchemaName=schema_name)
            return str(schema["Content"])

        except ClientError as ex:
            if ex.response.get("Error", {}).get("Code") != "NotFoundException":
                LOG.error(
                    "%s error calling describe_schema in registry %s for schema %s",
                    ex.response.get("Error", {}).get("Code"),
                    registry_name,
                    schema_name,
                )
                raise ex
            LOG.debug("Schema %s doesn't exist", schema_name)
            return ""
        except EndpointConnectionError as ex:
            LOG.error("Failure calling describe_schema in registry %s for schema %s", registry_name, schema_name)
            raise NotAvailableInRegion(SCHEMAS_NOT_AVAILABLE_IN_REGION_ERROR) from ex

    def check_registry_exists(self, registry_name: str) -> bool:
        """
        Gets a registry with the specified name

        Parameters
        ----------
        registry_name:
            The name of the registry to fetch
        Returns
        -------
        The specified registry, or None if it does not exist
        """
        try:
            LOG.debug("Describing registry %s.", registry_name)
            self._schemas_client.describe_registry(RegistryName=registry_name)
            return True  # If it didn't raise an exception, then it exists
        except ClientError as ex:
            if ex.response.get("Error", {}).get("Code") != "NotFoundException":
                LOG.error(
                    "%s error calling describe_registry in registry %s",
                    ex.response.get("Error", {}).get("Code"),
                    registry_name,
                )
                raise ex
            LOG.debug("Registry %s doesn't exist", registry_name)
        except EndpointConnectionError as ex:
            LOG.error("Failure calling describe_registry in registry %s", registry_name)
            raise NotAvailableInRegion(SCHEMAS_NOT_AVAILABLE_IN_REGION_ERROR) from ex
        return False

    def create_registry(self, registry_name: str):
        """
        Creates a new registry with the specified name

        Parameters
        ----------
        registry_name:
            The name of the registry to be created
        """
        try:
            LOG.debug("Creating registry %s.", registry_name)
            self._schemas_client.create_registry(RegistryName=registry_name)
            return True

        except ClientError as ex:
            if ex.response.get("Error", {}).get("Code") != "ConflictException":
                LOG.error(
                    "%s error calling create_registry for registry %s",
                    ex.response.get("Error", {}).get("Code"),
                    registry_name,
                )
                raise ex
            LOG.debug("Registry %s already exists", registry_name)

        except EndpointConnectionError as ex:
            LOG.error("Failure calling create_registry for registry %s", registry_name)
            raise NotAvailableInRegion(SCHEMAS_NOT_AVAILABLE_IN_REGION_ERROR) from ex
        return False

    def delete_schema(self, registry_name, schema_name) -> bool:
        """
        Deletes a schema from the EBSR

        Parameters
        ----------
        registry_name:
            The registry that contains the schema that will be deleted
        schema_name:
            The name of the schema to be deleted
        """
        try:
            LOG.debug("Deleting schema %s on registry %s.", schema_name, registry_name)
            self._schemas_client.delete_schema(RegistryName=registry_name, SchemaName=schema_name)
            return True

        except ClientError as ex:
            if ex.response.get("Error", {}).get("Code") != "NotFoundException":
                LOG.error(
                    "%s error when calling delete_delete schema with %s schema in %s registry",
                    ex.response.get("Error", {}).get("Code"),
                    schema_name,
                    registry_name,
                )
                raise ex
            LOG.debug("Schema %s doesn't exist so it couldn't be deleted", schema_name)

        except EndpointConnectionError as ex:
            LOG.error("Failure calling delete_schema for schema %s in registry %s", schema_name, registry_name)
            raise NotAvailableInRegion(SCHEMAS_NOT_AVAILABLE_IN_REGION_ERROR) from ex
        return False

    def delete_version(self, registry_name, schema_name, schema_version: str):
        """
        Delete a version of a schema

        Parameters
        ----------
        registry_name:
            The registry that contains the schema
        schema_name:
            The name of the schema
        schema_version:
            Version to be deleted
        """
        try:
            LOG.debug("Deleting version %s of schema %s on registry %s.", schema_version, schema_name, registry_name)
            self._schemas_client.delete_schema_version(
                RegistryName=registry_name,
                SchemaName=schema_name,
                SchemaVersion=schema_version,
            )
            return True

        except ClientError as ex:
            if ex.response.get("Error", {}).get("Code") != "NotFoundException":
                raise ex
            LOG.debug("Schema version %s of %s doesn't exist so it couldn't be deleted", schema_version, schema_name)
        except EndpointConnectionError as ex:
            LOG.error("Error when calling limit_versions")
            raise NotAvailableInRegion(SCHEMAS_NOT_AVAILABLE_IN_REGION_ERROR) from ex
        return False
