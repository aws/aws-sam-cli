"""
Context object used by `sam remote invoke` command
"""
import logging
from typing import Optional, cast

from samcli.commands.remote_invoke.exceptions import (
    AmbiguousResourceForRemoteInvoke,
    InvalidRemoteInvokeParameters,
    NoResourceFoundForRemoteInvoke,
    UnsupportedServiceForRemoteInvoke,
)
from samcli.lib.pipeline.bootstrap.resource import ARNParts
from samcli.lib.utils.boto_utils import BotoProviderType
from samcli.lib.utils.cloudformation import (
    CloudFormationResourceSummary,
    get_resource_summaries,
    get_resource_summary_from_physical_id,
)
from samcli.lib.utils.resources import AWS_LAMBDA_FUNCTION

LOG = logging.getLogger(__name__)


SUPPORTED_SERVICES = {"lambda": AWS_LAMBDA_FUNCTION}


class RemoteInvokeContext:

    _boto_client_provider: BotoProviderType
    _boto_resource_provider: BotoProviderType
    _stack_name: Optional[str]
    _resource_id: Optional[str]
    _resource_summary: Optional[CloudFormationResourceSummary]

    def __init__(
        self,
        boto_client_provider: BotoProviderType,
        boto_resource_provider: BotoProviderType,
        stack_name: Optional[str],
        resource_id: Optional[str],
    ):
        self._boto_resource_provider = boto_resource_provider
        self._boto_client_provider = boto_client_provider
        self._stack_name = stack_name
        self._resource_id = resource_id
        self._resource_summary = None

    def __enter__(self) -> "RemoteInvokeContext":
        self._populate_resource_summary()
        return self

    def __exit__(self, *args) -> None:
        pass

    def run(self):
        pass

    def _populate_resource_summary(self) -> None:
        if not self._stack_name and not self._resource_id:
            raise InvalidRemoteInvokeParameters("Either --stack-name or --resource-id parameter should be provided")

        if not self._resource_id:
            # no resource id provided, list all resources from stack and try to find one
            self._resource_summary = self._get_single_resource_from_stack()
            self._resource_id = self._resource_summary.logical_resource_id

        if not self._stack_name:
            # no stack name provided, resource id should be physical id so that we can use it
            self._resource_summary = self._get_from_physical_resource_id()

    def _get_single_resource_from_stack(self) -> CloudFormationResourceSummary:
        """
        Queries all resources from stack with its type,
        and returns its information if stack has only one resource from that type (including nested stacks)
        """
        resource_summaries = get_resource_summaries(
            self._boto_resource_provider, self._boto_client_provider, cast(str, self._stack_name), {AWS_LAMBDA_FUNCTION}
        )

        if len(resource_summaries) == 1:
            for logical_id, resource_summary in resource_summaries.items():
                LOG.debug("Using %s resource for remote invocation (%s)", logical_id, resource_summary)
                return resource_summary
        elif len(resource_summaries) > 1:
            raise AmbiguousResourceForRemoteInvoke(
                f"{self._stack_name} contains more than one resource that could be used with remote invoke, "
                f"please provide --resource-id to resolve ambiguity."
            )

        raise NoResourceFoundForRemoteInvoke(
            f"{self._stack_name} stack has no resources that can be used with remote invoke."
        )

    def _get_from_physical_resource_id(self) -> CloudFormationResourceSummary:
        resource_id = cast(str, self._resource_id)
        try:
            resource_arn = ARNParts(resource_id)
            service_from_arn = resource_arn.service

            if service_from_arn not in SUPPORTED_SERVICES:
                raise UnsupportedServiceForRemoteInvoke(
                    f"{service_from_arn} is not supported service, "
                    f"please use an ARN for following services, {SUPPORTED_SERVICES}"
                )

            return CloudFormationResourceSummary(
                cast(str, SUPPORTED_SERVICES.get(service_from_arn)),
                resource_id,
                resource_id,
            )
        except ValueError:
            LOG.debug(
                "Given %s is not an ARN, trying to get resource information from CloudFormation", self._resource_id
            )
            resource_summary = get_resource_summary_from_physical_id(self._boto_client_provider, resource_id)
            if not resource_summary:
                raise AmbiguousResourceForRemoteInvoke(
                    f"Can't find exact resource information with given {self._resource_id}. "
                    f"Please provide full resource ARN or --stack-name to resolve the ambiguity."
                )
            return resource_summary
