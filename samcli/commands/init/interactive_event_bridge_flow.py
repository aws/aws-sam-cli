"""
Isolates interactive init prompt flow for event bridge.
"""

import click

from samcli.lib.schemas.schemas_cli_message_generator import (
    construct_cli_display_message_for_schemas,
    construct_cli_display_message_for_registries,
)
from samcli.lib.schemas.schemas_api_caller import SchemasApiCaller
from samcli.lib.schemas.schemas_aws_config import get_schemas_client, get_aws_configuration_choice
from samcli.lib.schemas.cli_paginator import do_paginate_cli
from samcli.lib.schemas.schemas_constants import (
    SCHEMAS_REGISTRY,
    SCHEMA_NAME,
    EVENT_BRIDGE_SOURCE,
    EVENT_BRIDGE_SOURCE_DETAIL_TYPE,
    PAGE_LIMIT,
    SCHEMA_ROOT,
)


def get_schema_template_details(schemas_api_caller):
    """
    Calls schemas APIs to fetch available selection and returns schema details based on user selection.
    :param schemas_api_caller:
    :return:
    """
    registry_name = _get_registry_cli_choice(schemas_api_caller)
    schema_full_name = _get_schema_cli_choice(schemas_api_caller, registry_name)
    schema_latest_version = schemas_api_caller.get_latest_schema_version(registry_name, schema_full_name)
    get_schema_metadata_response = schemas_api_caller.get_schema_metadata(registry_name, schema_full_name)
    return {
        "registry_name": registry_name,
        "schema_full_name": schema_full_name,
        "schema_version": schema_latest_version,
        "event_source": get_schema_metadata_response["event_source"],
        "event_source_detail_type": get_schema_metadata_response["event_source_detail_type"],
        "schema_root_name": get_schema_metadata_response["schema_root_name"],
        "schemas_package_hierarchy": get_schema_metadata_response["schemas_package_hierarchy"],
    }


def _get_registry_cli_choice(schemas_api_caller):
    """Returns registry choice if one registry is present otherwise prompt for selection"""
    registries = _fetch_available_registries(schemas_api_caller, dict(), None)
    registry_pages = registries["registry_pages"]
    # If only one registry don't prompt for choice
    if len(registry_pages) == 1 and len(registry_pages.get(0)) == 1:
        return registry_pages.get(0)[0]

    # more than one registries
    click.echo("Which Schema Registry would you like to use?")
    next_token = registries.get("next_token")
    is_last_page = next_token is None
    return _prompt_for_registry_choice(
        schemas_api_caller, registry_pages, 0, next_token, is_last_page, last_page_number=None
    )


def _prompt_for_registry_choice(
    schemas_api_caller, registry_pages, page_to_render, next_token, is_last_page, last_page_number
):
    # construct CLI message
    cli_display_message = construct_cli_display_message_for_registries(page_to_render + 1, last_page_number)

    # get customer decision
    cli_response = do_paginate_cli(registry_pages, page_to_render, PAGE_LIMIT, is_last_page, cli_display_message)

    # user selected item
    if cli_response.get("choice") is not None:
        return cli_response.get("choice")

    # user decided to paginate
    page_to_render = cli_response.get("page_to_render")
    if registry_pages.get(page_to_render) is None:
        registries = _fetch_available_registries(schemas_api_caller, registry_pages, next_token)
        registry_pages = registries["registry_pages"]
        next_token = registries.get("next_token")
        is_last_page = next_token is None
    if is_last_page and last_page_number is None:
        last_page_number = page_to_render + 1
    return _prompt_for_registry_choice(
        schemas_api_caller, registry_pages, page_to_render, next_token, is_last_page, last_page_number
    )


def _get_schema_cli_choice(schemas_api_caller, registry_name):
    """Returns registry registry choice if one registry is present otherwise prompt for  selection"""
    schemas = _fetch_available_schemas(schemas_api_caller, registry_name, dict(), None)
    schema_pages = schemas["schema_pages"]
    # If only one schema don't prompt for choice
    if len(schema_pages) == 1 and len(schema_pages.get(0)) == 1:
        return schema_pages.get(0)[0]

    # more than one schema
    click.echo("\nWhich Schema would you like to use?")
    next_token = schemas.get("next_token")
    is_last_page = next_token is None
    return _prompt_for_schemas_choice(
        schemas_api_caller, registry_name, schema_pages, 0, next_token, is_last_page, last_page_number=None
    )


def _prompt_for_schemas_choice(
    schemas_api_caller, registry_name, schema_pages, page_to_render, next_token, is_last_page, last_page_number
):
    # construct CLI message
    cli_display_message = construct_cli_display_message_for_schemas(page_to_render + 1, last_page_number)

    # get customer decision
    cli_response = do_paginate_cli(schema_pages, page_to_render, PAGE_LIMIT, is_last_page, cli_display_message)

    # user selected item
    if cli_response.get("choice") is not None:
        return cli_response["choice"]

    # user decided to paginate
    page_to_render = cli_response.get("page_to_render")
    if schema_pages.get(page_to_render) is None:
        schemas = _fetch_available_schemas(schemas_api_caller, registry_name, schema_pages, next_token)
        schema_pages = schemas["schema_pages"]
        next_token = schemas.get("next_token")
        is_last_page = next_token is None
    if is_last_page and last_page_number is None:
        last_page_number = page_to_render + 1
    return _prompt_for_schemas_choice(
        schemas_api_caller, registry_name, schema_pages, page_to_render, next_token, is_last_page, last_page_number
    )


def _fetch_available_schemas(schemas_api_caller, registry_name, schema_pages, next_token):
    """calls schemas api fetch schemas for given registry. Two CLI pages are fetched at a time."""
    list_schemas_response = schemas_api_caller.list_schemas(registry_name, next_token, PAGE_LIMIT)
    schemas = list_schemas_response["schemas"]

    # divided response into pages
    pages = _construct_cli_page(schemas, PAGE_LIMIT)
    for page in range(0, len(pages)):
        schema_pages.update({len(schema_pages): pages.get(page)})
    next_token = list_schemas_response.get("next_token")
    return {"schema_pages": schema_pages, "next_token": next_token}


def _fetch_available_registries(schemas_api_caller, registry_pages, next_token):
    """calls schemas api to fetch registries. Two CLI pages are fetched at a time."""
    list_registries_response = schemas_api_caller.list_registries(next_token, PAGE_LIMIT)
    registries = list_registries_response["registries"]

    # sort registries alphabetically by name
    registries.sort()

    # divided response into pages
    pages = _construct_cli_page(registries, PAGE_LIMIT)
    for page in range(0, len(pages)):
        registry_pages.update({len(registry_pages): pages.get(page)})
    next_token = list_registries_response.get("next_token")
    return {"registry_pages": registry_pages, "next_token": next_token}


def _construct_cli_page(items, item_per_page):
    """Responsible for splitting items into CLI pages.
    Currently CLI pages are list of dictionary [0:{0:s1, 1:s2: 3:s3}, 1: {4:s4, 5:s5: 6:s6}]
    We maintain the page detail and item index details."""
    pages = [
        items[i * item_per_page : (i + 1) * item_per_page]
        for i in range((len(items) + item_per_page - 1) // item_per_page)
    ]
    index = 0
    schema_dict = dict()
    for page in pages:
        schema_dict.update({index: page})
        index = index + 1

    return schema_dict


def get_schemas_template_parameter(schema_template_details):
    """Schemas cookiecutter template parameter mapping"""
    return {
        SCHEMAS_REGISTRY: schema_template_details["registry_name"],
        SCHEMA_NAME: schema_template_details["schema_root_name"],
        EVENT_BRIDGE_SOURCE: schema_template_details["event_source"],
        EVENT_BRIDGE_SOURCE_DETAIL_TYPE: schema_template_details["event_source_detail_type"],
        SCHEMA_ROOT: schema_template_details["schemas_package_hierarchy"],
    }


def get_schemas_api_caller():
    aws_configuration = get_aws_configuration_choice()
    schemas_client = get_schemas_client(aws_configuration["profile"], aws_configuration["region"])
    return SchemasApiCaller(schemas_client)
