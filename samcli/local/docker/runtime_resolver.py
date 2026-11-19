"""
Resolver for customer-managed runtime (CMR) invoke images.

A function with ``Runtime: custom`` carries no language-specific base image of its own. Its invoke
image is identified by the ``RuntimeConfig`` template property (the published runtime's
RuntimeArn/RuntimeAlias). This module resolves that configuration to a concrete image reference for
local invoke.

Resolution precedence:
  1. If the caller supplied an image with ``--invoke-image``, use it as-is -- this is the Tier 1 path
     and requires no network call or runtime model.
  2. Otherwise the image is resolved from ``RuntimeConfig`` via the Lambda runtime APIs:
     GetRuntimeAlias (RuntimeArn + RuntimeAlias -> RuntimeVersion), then GetRuntimeVersion
     (RuntimeArn + RuntimeVersion -> ResolvedUri).

Either way the image is then pulled with Docker's own credentials, as for any other image.
"""

import logging
from typing import Any, Dict, Optional

import boto3
from botocore.exceptions import BotoCoreError, ClientError, NoCredentialsError

from samcli.commands.local.cli_common.user_exceptions import CredentialsRequired, ResourceNotFound
from samcli.lib.utils.arn_utils import ARNParts, InvalidArnValue
from samcli.local.docker.exceptions import RuntimeResolutionException

LOG = logging.getLogger(__name__)


def resolve_custom_runtime_image(
    runtime_config: Optional[Dict], supplied_image: Optional[str], lambda_client: Optional[Any] = None
) -> str:
    """
    Resolve the invoke image for a customer-managed runtime (``Runtime: custom``) function.

    Parameters
    ----------
    runtime_config : dict, optional
        The function's ``RuntimeConfig`` template property, carrying ``RuntimeArn`` and
        ``RuntimeAlias``.
    supplied_image : str, optional
        An image the caller supplied with ``--invoke-image``.
    lambda_client : boto3.client('lambda-core'), optional
        Boto3 client for the Lambda runtime APIs. Created on demand when not provided.

    Returns
    -------
    str
        The image reference to use for local invoke.

    Raises
    ------
    samcli.local.docker.exceptions.RuntimeResolutionException
        If no image was supplied and ``RuntimeConfig`` lacks a RuntimeArn or RuntimeAlias.
    samcli.commands.local.cli_common.user_exceptions.CredentialsRequired
        When credentials are missing or not permitted to read the runtime.
    samcli.commands.local.cli_common.user_exceptions.ResourceNotFound
        When the runtime, alias or version does not exist.
    """
    # Tier 1: an explicitly supplied image always wins and needs no resolution.
    if supplied_image:
        LOG.debug("Using supplied invoke image for custom runtime: %s", supplied_image)
        return supplied_image

    # Distinct shapes reach this point, each with its own user-facing message:
    #   1. No RuntimeConfig at all: the user set Runtime: custom and forgot RuntimeConfig. sam build
    #      doesn't enforce the pairing; sam validate and sam deploy do.
    #   2. RuntimeConfig is not a mapping (for example !Ref to a String parameter).
    #   3. RuntimeConfig, or one of its fields, is an intrinsic SAM CLI cannot resolve locally (for
    #      example Fn::ImportValue), which reaches the resolver as a dict rather than a value.
    #   4. RuntimeConfig is a mapping but a field is missing or empty.
    if not runtime_config:
        raise RuntimeResolutionException(
            "Unable to resolve an invoke image for the 'custom' runtime: the function has no "
            "RuntimeConfig. Add RuntimeConfig with RuntimeArn and RuntimeAlias, or pass an image "
            "with --invoke-image."
        )
    if not isinstance(runtime_config, dict):
        raise RuntimeResolutionException(
            "Unable to resolve an invoke image for the 'custom' runtime: RuntimeConfig must be a mapping "
            "with RuntimeArn and RuntimeAlias."
        )
    if any(key == "Ref" or str(key).startswith("Fn::") for key in runtime_config):
        raise RuntimeResolutionException(
            "Unable to resolve an invoke image for the 'custom' runtime: RuntimeConfig RuntimeArn and "
            "RuntimeAlias must be literal values or template parameters to be resolved locally."
        )
    runtime_arn = runtime_config.get("RuntimeArn")
    runtime_alias = runtime_config.get("RuntimeAlias")
    missing = [name for name, value in (("RuntimeArn", runtime_arn), ("RuntimeAlias", runtime_alias)) if not value]
    if missing:
        raise RuntimeResolutionException(
            "Unable to resolve an invoke image for the 'custom' runtime: RuntimeConfig is missing {}.".format(
                " and ".join(missing)
            )
        )
    if not isinstance(runtime_arn, str) or not isinstance(runtime_alias, str):
        raise RuntimeResolutionException(
            "Unable to resolve an invoke image for the 'custom' runtime: RuntimeConfig RuntimeArn and "
            "RuntimeAlias must be literal values or template parameters to be resolved locally."
        )

    # Tier 2: resolve alias -> version -> image URI via the Lambda runtime APIs, which the SDK ships as their
    # own service, lambda-core (boto3 1.44.3 and later), not as part of the lambda client.
    # Typed as Any: the bundled boto3 stubs do not yet model the CMR runtime operations. Credentials come from
    # boto3's default session (--profile), like the layer downloader, but the call goes to the runtime's own
    # region: a runtime is only known in the region its ARN names.
    try:
        region: Optional[str] = ARNParts(runtime_arn).region or None
    except InvalidArnValue:
        region = None
    client: Any = lambda_client or boto3.client("lambda-core", region_name=region)
    runtime = "runtime {} alias {}".format(runtime_arn, runtime_alias)
    try:
        alias = client.get_runtime_alias(RuntimeName=runtime_arn, Name=runtime_alias)
        version = client.get_runtime_version(RuntimeName=runtime_arn, Name=alias.get("RuntimeVersion"))
    except NoCredentialsError as ex:
        raise CredentialsRequired(
            "Resolving the runtime image for RuntimeConfig requires AWS credentials. Configure credentials, "
            "for example with --profile."
        ) from ex
    except ClientError as e:
        error = e.response.get("Error", {})
        message = error.get("Message") or str(e)
        if error.get("Code") == "AccessDeniedException":
            raise CredentialsRequired("Not allowed to look up {}: {}".format(runtime, message)) from e
        if error.get("Code") == "ResourceNotFoundException":
            raise ResourceNotFound(
                "Runtime {} alias {} was not found: {}".format(runtime_arn, runtime_alias, message)
            ) from e
        raise RuntimeResolutionException("Could not look up {}: {}".format(runtime, message)) from e
    except BotoCoreError as e:
        # Errors that never reached Lambda, such as no network.
        raise RuntimeResolutionException("Could not look up {}: {}".format(runtime, e)) from e

    # ResolvedUri is a required member of the GetRuntimeVersion response.
    resolved_uri: str = version["ResolvedUri"]
    LOG.info("Using runtime image %s (RuntimeAlias '%s')", resolved_uri, runtime_alias)
    return resolved_uri
