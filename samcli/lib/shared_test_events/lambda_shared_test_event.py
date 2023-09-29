"""For operations specific to Lambda shared test event schemas"""

import json
import logging
from json import JSONDecodeError
from typing import Any

import botocore

from samcli.commands.exceptions import SchemasApiException
from samcli.commands.local.cli_common.user_exceptions import ResourceNotFound, SchemaPermissionsError
from samcli.commands.remote.exceptions import (
    DuplicateEventName,
    EventTooLarge,
    InvalidSchema,
    ResourceNotSupportedForTestEvents,
)
from samcli.lib.schemas.schemas_api_caller import SchemasApiCaller
from samcli.lib.utils.cloudformation import CloudFormationResourceSummary
from samcli.lib.utils.resources import AWS_LAMBDA_FUNCTION

LAMBDA_TEST_EVENT_REGISTRY = "lambda-testevent-schemas"
MIN_EVENTS = 1
MAX_SCHEMA_VERSIONS = 5
# 6MB Lambda invocation payload limit
MAX_EVENT_SIZE = 6144000
OPEN_API_TYPE = "OpenApi3"
SCHEMA_PERMISSIONS_ERROR = """
    You don't have the neccesary permissions to create shareable test events.

    Update your role to have the necessary permissions or change your event sharing settings to private.

    Learn more: https://docs.aws.amazon.com/lambda/latest/dg/testing-functions.html#creating-shareable-events
"""
LOG = logging.getLogger(__name__)


class NoPermissionExceptionWrapper(object):
    """
    Class that wraps an ApiCaller object, to catch a "ForbiddenException"
    and throw our own exception with a custom message in that case
    """

    def __init__(self, api: SchemasApiCaller):
        self.api: SchemasApiCaller = api

    def __getattr__(self, attr):
        def wrapper(*args, **kwargs):
            try:
                return getattr(self.api, attr)(*args, **kwargs)
            except botocore.exceptions.ClientError as ex:
                if ex.response.get("Error", {}).get("Code") == "ForbiddenException":
                    raise SchemaPermissionsError(SCHEMA_PERMISSIONS_ERROR)
                raise

        return wrapper

    @classmethod
    def wrap(cls, api: SchemasApiCaller) -> SchemasApiCaller:
        # The wrapper behaves effectively like the SchemasApiCaller it's wrapping
        wrapper: SchemasApiCaller = NoPermissionExceptionWrapper(api)  # type: ignore
        return wrapper


class LambdaSharedTestEvent:
    def __init__(self, schema_api_caller: SchemasApiCaller, lambda_client):
        self._api_caller: SchemasApiCaller = NoPermissionExceptionWrapper.wrap(schema_api_caller)
        self._lambda_client = lambda_client

    def _validate_schema_dict(self, schema_dict: dict):
        # For our purposes, the only field we care exists is "components"
        # All other parts of the schema are generated externally, so we do not verify these
        if "components" not in schema_dict:
            raise InvalidSchema(f"Schema {json.dumps(schema_dict)} is not valid")

    def _validate_event_size(self, event: str):
        """
        Raises an EventTooLarge exception if the event is bigger than accepted

        Parameters
        ----------
        event : str
            Contents of the event to validate

        Raises
        ------
        EventTooLarge
            When the event is bigger than the accepted Lambda invocation payload size
        """
        if len(event.encode("utf8")) > MAX_EVENT_SIZE:
            raise EventTooLarge(
                "Event is bigger than the accepted Lambda invocation payload size. "
                + "Learn more at https://docs.aws.amazon.com/lambda/latest/dg/gettingstarted-limits.html#function-configuration-deployment-and-execution"
            )

    def _get_schema_name(self, function_resource: CloudFormationResourceSummary) -> str:
        """
        Get the schema name for a specific function according to the Lambda convention

        Parameters
        ----------
        function_resource : CloudFormationResourceSummary
            The function resource
        """
        if function_resource.resource_type != AWS_LAMBDA_FUNCTION:
            raise ResourceNotSupportedForTestEvents(
                f"Resource type {function_resource.resource_type} is not supported for remote test events."
            )
        function_name = function_resource.physical_resource_id
        if function_name.startswith("arn:"):
            # If it's an ARN, we check that the function exists and get its name.
            try:
                function_config = self._lambda_client.get_function_configuration(FunctionName=function_name)
                function_name = function_config["FunctionName"]
            except botocore.exceptions.ClientError as ex:
                if ex.response.get("Error", {}).get("Code") == "ResourceNotFoundException":
                    raise ResourceNotFound(f"Function not found when trying to read events: {function_name}")
                raise

        return f"_{function_name}-schema"

    def limit_versions(self, schema_name: str, registry_name: str = LAMBDA_TEST_EVENT_REGISTRY):
        """
        Delete the oldest existing version if there are more than MAX_SCHEMA_VERSIONS.

        Parameters
        ----------
        schema_name : str
            Schema to limit versions
        registry_name : str
            Registry name
        """

        schema_version_list = self._api_caller.list_schema_versions(registry_name, schema_name)

        if len(schema_version_list) >= MAX_SCHEMA_VERSIONS:
            version_to_delete = schema_version_list[0]  # Oldest version
            LOG.debug(
                "Over %s versions, deleting version %s",
                MAX_SCHEMA_VERSIONS,
                version_to_delete,
            )
            self._api_caller.delete_version(registry_name, schema_name, version_to_delete)

    def add_event_to_schema(self, schema: str, event: str, event_name: str, replace_if_exists: bool = False) -> str:
        """
        Adds an event to a schema

        Parameters
        ---------
        schema:
            The schema the event will be added to
        event:
            The event that will be added to the schema
        event_name:
            The name of the event that will be added to the schema

        Returns
        -------
        The updated schema with the event added to the "examples" section
        """
        try:
            self._validate_event_size(event)
            schema_dict = json.loads(schema)
            self._validate_schema_dict(schema_dict)

            event_dict = json.loads(event)

            # this occurs when we freshly generate a schema
            if "examples" not in schema_dict["components"]:
                schema_dict["components"]["examples"] = {}

            if event_name in schema_dict["components"]["examples"] and not replace_if_exists:
                raise DuplicateEventName(f"Event {event_name} already exists. You can replace it with `--force`.")

            schema_dict["components"]["examples"][event_name] = {
                "value": event_dict,
            }

            schema = json.dumps(schema_dict)

            return schema

        except JSONDecodeError as ex:
            LOG.error("Error parsing schema when adding event %s", event_name)
            raise SchemasApiException(
                "Parse error reading the content from Schemas response. "
                "This should not be possible, please raise an issue."
            ) from ex

    def get_event_from_schema(self, schema: str, event_name: str) -> Any:
        """
        Gets the specified event from the provided schema

        Parameters
        ----------
        schema:
            the schema string that contains the event
        event_name:
            the name of the event to retrieve from the schema
        Returns
        -------
        The event data of the event "event_name"
        """
        try:
            schema_dict = json.loads(schema)

            self._validate_schema_dict(schema_dict)
            existing_events = schema_dict["components"].get("examples", {})
            if event_name not in existing_events or "value" not in existing_events[event_name]:
                raise ResourceNotFound(f"Event {event_name} not found")

            # can use square brackets here since we know each of these subdicts exist
            return existing_events[event_name]["value"]

        except JSONDecodeError as ex:
            LOG.error("Error decoding schema when getting event %s", event_name)
            raise SchemasApiException(
                "Parse error reading the content from Schemas response. "
                "This should not be possible, please raise an issue."
            ) from ex

    def remove_event(self, schema: str, event_name: str) -> str:
        """
        Removes an event from a schema dict. If there are none, returns None

        Parameters
        ----------
        schema:
            The schema the event will be removed from
        event_name:
            The name of the event that will be removed from the schema
        Returns
        -------
        The updated schema with the event removed, or None of the schema does not contain the event
        """
        try:
            schema_dict = json.loads(schema)

            self._validate_schema_dict(schema_dict)

            if event_name not in schema_dict["components"].get("examples", {}):
                raise ResourceNotFound(f"Event {event_name} not found")

            if len(schema_dict["components"]["examples"]) <= MIN_EVENTS:
                LOG.debug("event %s is only event in schema, entire schema will be deleted", event_name)
                return ""

            schema_dict["components"]["examples"].pop(event_name)

            schema = json.dumps(schema_dict)
            return schema

        except JSONDecodeError as ex:
            LOG.error("Error parsing schema while removing event %s", event_name)
            raise SchemasApiException(
                "Parse error reading the content from Schemas response. "
                "This should not be possible, please raise an issue."
            ) from ex

    def create_event(
        self,
        event_name: str,
        function_resource: CloudFormationResourceSummary,
        event_data: str,
        force: bool = False,
        registry_name: str = LAMBDA_TEST_EVENT_REGISTRY,
    ) -> str:
        """
        Generates a new event and adds it to the EBSR

        Parameters
        ----------
        event_name: str
            The name of the event to be created
        function_resource: CloudFormationResourceSummary
            The function where the event will be created
        event_data: str
            The JSON data of the event to be created
        registry_name: str
            The name of the registry that contains the schema
        """
        api_caller = self._api_caller

        if not api_caller.check_registry_exists(registry_name):
            api_caller.create_registry(registry_name)

        schema_name = self._get_schema_name(function_resource)
        original_schema = api_caller.get_schema(registry_name, schema_name)

        if original_schema:
            LOG.debug("Schema %s already exists, adding event %s", schema_name, event_name)
            self.limit_versions(schema_name, registry_name)
            schema = self.add_event_to_schema(original_schema, event_data, event_name, replace_if_exists=force)
            api_caller.update_schema(schema, registry_name, schema_name, OPEN_API_TYPE)
        else:
            LOG.debug("Schema %s does not already exist, creating new", schema_name)
            schema = api_caller.discover_schema(event_data, OPEN_API_TYPE)
            schema = self.add_event_to_schema(schema, event_data, event_name)
            api_caller.create_schema(schema, registry_name, schema_name, OPEN_API_TYPE)

        return schema

    def delete_event(
        self,
        event_name: str,
        function_resource: CloudFormationResourceSummary,
        registry_name: str = LAMBDA_TEST_EVENT_REGISTRY,
    ):
        """
        Deletes a remote test event (and the schema if it contains only one event)

        Parameters
        ----------
        event_name: str
            The name of the event to be deleted
        function_resource: CloudFormationResourceSummary
            The function that will have the event deleted
        registry_name: str
            The name of the registry that contains the schema
        """
        api_caller = self._api_caller

        if not api_caller.check_registry_exists(registry_name):
            raise ResourceNotFound(f"{registry_name} registry not found. There are no saved events.")

        schema_name = self._get_schema_name(function_resource)
        schema = api_caller.get_schema(registry_name, schema_name)
        function_name = function_resource.logical_resource_id

        if not schema:
            raise ResourceNotFound(f"No events found for function {function_name}")

        schema = self.remove_event(schema, event_name)

        if not schema:
            LOG.debug("Only one event in schema %s, deleting schema for function %s", schema_name, function_name)
            api_caller.delete_schema(registry_name, schema_name)
        else:
            LOG.debug("Multiple events in schema %s, updating schema for function %s", schema_name, function_name)
            self.limit_versions(schema_name, registry_name)
            api_caller.update_schema(schema, registry_name, schema_name, OPEN_API_TYPE)

    def get_event(
        self,
        event_name: str,
        function_resource: CloudFormationResourceSummary,
        registry_name: str = LAMBDA_TEST_EVENT_REGISTRY,
    ) -> str:
        """
        Returns a remote test event

        Parameters
        ----------
        event_name: str
            The name of the event to be fetched
        function_resource: CloudFormationResourceSummary
            The function that has the event
        registry_name: str
            The name of the registry that contains the schema
        Returns
        -------
        The JSON data of the event
        """
        api_caller = self._api_caller

        if not api_caller.check_registry_exists(registry_name):
            raise ResourceNotFound(f"{registry_name} registry not found. There are no saved events.")

        schema_name = self._get_schema_name(function_resource)
        schema = api_caller.get_schema(registry_name, schema_name)
        function_name = function_resource.logical_resource_id

        if not schema:
            raise ResourceNotFound(f"No events found for function {function_name}")

        event = self.get_event_from_schema(schema, event_name)

        try:
            return json.dumps(event)

        except JSONDecodeError as ex:
            LOG.error("Error parsing event %s from schema %s", event_name, schema_name)
            raise SchemasApiException(
                "Parse error reading the content from Schemas response. "
                "This should not be possible, please raise an issue."
            ) from ex

    def list_events(
        self,
        function_resource: CloudFormationResourceSummary,
        registry_name: str = LAMBDA_TEST_EVENT_REGISTRY,
    ) -> str:
        """_summary_

        Parameters
        ----------
        function_resource : CloudFormationResourceSummary
            The function to list the test events from
        registry_name : str, optional
            Registry name, by default LAMBDA_TEST_EVENT_REGISTRY

        Returns
        -------
        str
            Function's event names, separated by a new line
        """
        api_caller = self._api_caller

        if not api_caller.check_registry_exists(registry_name):
            raise ResourceNotFound(f"{registry_name} registry not found. There are no saved events.")

        schema_name = self._get_schema_name(function_resource)
        schema = api_caller.get_schema(registry_name, schema_name)
        function_name = function_resource.logical_resource_id

        if not schema:
            raise ResourceNotFound(f"No events found for function {function_name}")

        try:
            schema_dict = json.loads(schema)
            return "\n".join(schema_dict.get("components", {}).get("examples", {}).keys())
        except JSONDecodeError as ex:
            LOG.error("Error parsing schema %s", schema_name)
            raise SchemasApiException(
                "Parse error reading the content from Schemas response. "
                "This should not be possible, please raise an issue."
            ) from ex
