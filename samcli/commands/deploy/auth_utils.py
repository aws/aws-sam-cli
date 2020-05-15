"""
Utilities for checking authorization of certain resource types
"""
import logging

from samcli.commands.local.lib.swagger.reader import SwaggerReader
from samcli.lib.providers.sam_function_provider import SamFunctionProvider

LOG = logging.getLogger(__name__)


def auth_per_resource(parameter_overrides, template_dict):
    """
    Check if authentication has been set for the function resources defined in the template that have `Api` Event type.

    Parameters
    ----------
    parameter_overrides: dict
        list of parameter overrides for the parameters defined in the template
    template_dict: dict
        Raw dictionary of the defined SAM template

    Returns
    -------

    List of tuples per function resource that have the `Api` or `HttpApi` event types, that describes the resource name
    and if authorization is required per resource.

    """

    _auth_per_resource = []

    sam_functions = SamFunctionProvider(
        template_dict=template_dict, parameter_overrides=parameter_overrides, ignore_code_extraction_warnings=True
    )
    for sam_function in sam_functions.get_all():
        # Only check for auth if there are function events defined.
        if sam_function.events:
            _auth_resource_event(sam_functions, sam_function, _auth_per_resource)

    return _auth_per_resource


def _auth_resource_event(sam_functions, sam_function, auth_resource_list):
    """

    Parameters
    ----------
    sam_functions: List of all functions with intrinscis resolved.
    sam_function: Current function which has all intrinsics resolved.
    auth_resource_list: List of tuples with function name and auth. eg: [("Name", True)]

    Returns
    -------

    """
    for event in sam_function.events.values():
        for event_type, identifier in [("Api", "RestApiId"), ("HttpApi", "ApiId")]:
            if event.get("Type") == event_type:
                # Is there any auth defined directly on the function resource?
                # NOTE(sriram-mv): How do we check this in more detail?
                # Currently just checking for presence of Auth, not the details.
                # https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/sam-property-function-apifunctionauth.html
                # https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/sam-property-function-httpapifunctionauth.html
                if event.get("Properties", {}).get("Auth", False):
                    auth_resource_list.append((sam_function.name, True))
                # Is there any auth defined on the referred http api or serverless api through the `id` construct?
                elif _auth_id(sam_functions.resources, event.get("Properties", {}), identifier):
                    auth_resource_list.append((sam_function.name, True))
                else:
                    auth_resource_list.append((sam_function.name, False))


def _auth_id(resources_dict, event_properties, identifier):
    """

    Parameters
    ----------
    resources_dict: dict
        Resolved resources defined in the SAM Template
    event_properties: dict
        Properties of given event supplied to a function resource
    identifier: str
        Id: `ApiId` or `RestApiId`

    Returns
    -------
    bool
        Returns if the given identifier under the event properties maps to a resource and has authorization enabled.

    """
    resource_name = event_properties.get(identifier, "")
    api_resource = resources_dict.get(resource_name, {})
    return any(
        [
            api_resource.get("Properties", {}).get("Auth", False),
            _auth_definition_body_and_uri(
                definition_body=api_resource.get("Properties", {}).get("DefinitionBody", {}),
                definition_uri=api_resource.get("Properties", {}).get("DefinitionUri", None),
            ),
        ]
    )


def _auth_definition_body_and_uri(definition_body, definition_uri):
    """

    Parameters
    ----------
    definition_body: dict
        inline definition body defined in the template
    definition_uri: string
        Either an s3 url or a local path to a definition uri

    Returns
    -------
    bool
        Is security defined on the swagger or not?


    """

    reader = SwaggerReader(definition_body=definition_body, definition_uri=definition_uri)
    swagger = reader.read()
    _auths = []
    if not swagger:
        swagger = {}
    # NOTE(sriram-mv): Authorization and Authentication is indicated by the `security` scheme.
    # https://swagger.io/docs/specification/authentication/
    for _, verb in swagger.get("paths", {}).items():
        for _property in verb.values():
            # If there are instrinsics in play, they may not be resolved yet.
            if isinstance(_property, dict):
                _auths.append(bool(_property.get("security", False)))

    _auths.append(bool(swagger.get("security", False)))

    if swagger:
        LOG.debug("Auth checks done on swagger are not exhaustive!")

    # This is not an exhaustive check, but to check if there is some form of security setup.
    return any(_auths)
