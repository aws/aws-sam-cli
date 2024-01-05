"""Module containing functions to publish or update application."""

import copy
import logging
import re

import boto3
from botocore.exceptions import ClientError

from samcli.yamlhelper import yaml_dump

from .application_metadata import ApplicationMetadata
from .exceptions import (
    DuplicateSemanticVersionError,
    InvalidS3UriError,
    MissingSemanticVersionError,
    S3PermissionsRequired,
    ServerlessRepoClientError,
)
from .parser import get_app_metadata, parse_application_id, parse_template, strip_app_metadata

LOG = logging.getLogger(__name__)

CREATE_APPLICATION = "CREATE_APPLICATION"
UPDATE_APPLICATION = "UPDATE_APPLICATION"
CREATE_APPLICATION_VERSION = "CREATE_APPLICATION_VERSION"


def publish_application(template, sar_client=None, fail_on_same_version=False):
    """
    Create a new application or new application version in SAR.

    Parameters
    ----------
    template: str | dict
        Content of a packaged YAML or JSON SAM template

    sar_client: boto3.client
        The boto3 client used to access SAR

    fail_on_same_version: bool
        Whether or not publish hard fails when a duplicate semantic version is provided

    Returns
    -------
    dict
        Dictionary containing application id, actions taken, and updated details

    Raises
    ------
        ValueError
            If the template is null

        ClientError
            If sar client operations fail

        MissingSemanticVersionError
            If --fail-on-same-version is set in sam publish command but no semantic version is provided

        DuplicateSemanticVersionError
            If --fail-on-same-version is set in sam publish command and the provided semantic version already exists
    """
    if not template:
        raise ValueError("Require SAM template to publish the application")

    if not sar_client:
        sar_client = boto3.client("serverlessrepo")

    template_dict = _get_template_dict(template)
    app_metadata = get_app_metadata(template_dict)
    stripped_template_dict = strip_app_metadata(template_dict)
    stripped_template = yaml_dump(stripped_template_dict)
    try:
        request = _create_application_request(app_metadata, stripped_template)
        response = sar_client.create_application(**request)
        application_id = response["ApplicationId"]
        actions = [CREATE_APPLICATION]
    except ClientError as e:
        if not _is_conflict_exception(e):
            raise _wrap_client_error(e)

        # Update the application if it already exists
        error_message = e.response["Error"]["Message"]
        application_id = parse_application_id(error_message)

        if fail_on_same_version:
            if not app_metadata.semantic_version:
                raise MissingSemanticVersionError(
                    "--fail-on-same-version is set, but no semantic version is specified.\n"
                    "Please provide a semantic version in either the "
                    "template metadata or with the --semantic-version option."
                )

            semantic_version = app_metadata.semantic_version

            # Check if the given semantic version already exists
            try:
                application_exists = _check_app_with_semantic_version_exists(
                    sar_client, application_id, semantic_version
                )
            except ClientError as e:
                raise _wrap_client_error(e)

            if application_exists:
                raise DuplicateSemanticVersionError(
                    f"Cannot publish version {semantic_version} for application "
                    f"{application_id} because it already exists"
                )

        try:
            request = _update_application_request(app_metadata, application_id)
            sar_client.update_application(**request)
            actions = [UPDATE_APPLICATION]
        except ClientError as e:
            raise _wrap_client_error(e)

        # Create application version if semantic version is specified
        if app_metadata.semantic_version:
            try:
                request = _create_application_version_request(app_metadata, application_id, stripped_template)
                sar_client.create_application_version(**request)
                actions.append(CREATE_APPLICATION_VERSION)
            except ClientError as e:
                if not _is_conflict_exception(e):
                    raise _wrap_client_error(e)

                LOG.warning(
                    "WARNING: Publishing with semantic version that already exists. This may cause issues deploying."
                )

    return {
        "application_id": application_id,
        "actions": actions,
        "details": _get_publish_details(actions, app_metadata.template_dict),
    }


def _check_app_with_semantic_version_exists(sar_client, application_id, semantic_version):
    """
    Checks if a given SAR application exists with a given semantic version

    Parameters
    ----------
    sar_client: boto3.client
        The boto3 client used to access SAR

    application_id: str
        Application Id to check

    semantic_version: str
        The semantic version to check with Application Id

    Returns
    -------
    bool
        Whether or not the given Application exists with the given semantic version

    Raises
    ------
    ClientError
        If the sar client operations fail

    """

    # SAR API does not have a direct method to check if an application exists
    # with a given semantic version, but if it does not exist, a NotFoundException is thrown.
    try:
        sar_client.get_application(ApplicationId=application_id, SemanticVersion=semantic_version)
        return True
    except ClientError as error:
        if error.response["Error"]["Code"] == "NotFoundException":
            return False
        else:
            raise error


def _get_template_dict(template):
    """
    Parse string template and or copy dictionary template.

    Parameters
    ----------
    template: str | dict
        Content of a packaged YAML or JSON SAM template

    Returns
    -------
    dict
        Template as a dictionary

    Raises
    ------
    ValueError
        If the supplied template is not a string or dictionary
    """
    if isinstance(template, str):
        return parse_template(template)

    if isinstance(template, dict):
        return copy.deepcopy(template)

    raise ValueError("Input template should be a string or dictionary")


def _create_application_request(app_metadata, template):
    """
    Construct the request body to create application.

    Parameters
    ----------
    app_metadata: ApplicationMetadata
        Object containing app metadata

    template: str
        A packaged YAML or JSON SAM template

    Returns
    -------
    dict
        SAR CreateApplication request body
    """
    app_metadata.validate(["author", "description", "name"])
    request = {
        "Author": app_metadata.author,
        "Description": app_metadata.description,
        "HomePageUrl": app_metadata.home_page_url,
        "Labels": app_metadata.labels,
        "LicenseBody": app_metadata.license_body,
        "LicenseUrl": app_metadata.license_url,
        "Name": app_metadata.name,
        "ReadmeBody": app_metadata.readme_body,
        "ReadmeUrl": app_metadata.readme_url,
        "SemanticVersion": app_metadata.semantic_version,
        "SourceCodeUrl": app_metadata.source_code_url,
        "SpdxLicenseId": app_metadata.spdx_license_id,
        "TemplateBody": template,
    }
    # Remove None values
    return {k: v for k, v in request.items() if v}


def _update_application_request(app_metadata, application_id):
    """
    Construct the request body to update application.

    Parameters
    ----------
    app_metadata: ApplicationMetadata
        Object containing app metadata

    application_id: str
        The Amazon Resource Name (ARN) of the application

    Returns
    -------
    dict
        SAR CreateApplication request body
    """
    request = {
        "ApplicationId": application_id,
        "Author": app_metadata.author,
        "Description": app_metadata.description,
        "HomePageUrl": app_metadata.home_page_url,
        "Labels": app_metadata.labels,
        "ReadmeBody": app_metadata.readme_body,
        "ReadmeUrl": app_metadata.readme_url,
    }
    return {k: v for k, v in request.items() if v}


def _create_application_version_request(app_metadata, application_id, template):
    """
    Construct the request body to create application version.

    Parameters
    ----------
    app_metadata: ApplicationMetadata
        Object containing app metadata

    application_id: str
        The Amazon Resource Name (ARN) of the application

    template: str
        A packaged YAML or JSON SAM template

    Returns
    -------
    dict
        SAR CreateApplication request body
    """
    app_metadata.validate(["semantic_version"])
    request = {
        "ApplicationId": application_id,
        "SemanticVersion": app_metadata.semantic_version,
        "SourceCodeUrl": app_metadata.source_code_url,
        "TemplateBody": template,
    }
    return {k: v for k, v in request.items() if v}


def _is_conflict_exception(e):
    """
    Check whether the botocore ClientError is ConflictException.

    Parameters
    ----------
    e: ClientError
        botocore exception

    Returns
    -------
    bool
        True if e is ConflictException, False otherwise
    """
    error_code = e.response["Error"]["Code"]
    return error_code == "ConflictException"


def _wrap_client_error(e):
    """
    Wrap botocore ClientError exception into ServerlessRepoClientError.

    Parameters
    ----------
    e: ClientError
        botocore exception

    Returns
    -------
    ServerlessRepoError
       S3PermissionsRequired or InvalidS3UriError or general ServerlessRepoClientError
    """
    error_code = e.response["Error"]["Code"]
    message = e.response["Error"]["Message"]

    if error_code == "BadRequestException":
        if "Failed to copy S3 object. Access denied:" in message:
            match = re.search("bucket=(.+?), key=(.+?)$", message)
            if match:
                return S3PermissionsRequired(bucket=match.group(1), key=match.group(2))
        if "Invalid S3 URI" in message:
            return InvalidS3UriError(message=message)

    return ServerlessRepoClientError(message=message)


def _get_publish_details(actions, app_metadata_template):
    """
    Get the changed application details after publishing.

    Parameters
    ----------
    actions: str | list
        Actions taken during publishing

    app_metadata_template: dict
        Original template definitions of app metadata

    Returns
    -------
    dict
        Updated fields and values of the application
    """
    if actions == [CREATE_APPLICATION]:
        return {k: v for k, v in app_metadata_template.items() if v}

    include_keys = [
        ApplicationMetadata.AUTHOR,
        ApplicationMetadata.DESCRIPTION,
        ApplicationMetadata.HOME_PAGE_URL,
        ApplicationMetadata.LABELS,
        ApplicationMetadata.README_URL,
        ApplicationMetadata.README_BODY,
    ]

    if CREATE_APPLICATION_VERSION in actions:
        # SemanticVersion and SourceCodeUrl can only be updated by creating a new version
        additional_keys = [ApplicationMetadata.SEMANTIC_VERSION, ApplicationMetadata.SOURCE_CODE_URL]
        include_keys.extend(additional_keys)
    return {k: v for k, v in app_metadata_template.items() if k in include_keys and v}
