"""
Remote Invoke factory to instantiate remote invoker for given resource
"""
import logging
from typing import Any, Callable, Dict, Optional

from samcli.lib.remote_invoke.remote_invoke_executors import RemoteInvokeExecutor
from samcli.lib.utils.cloudformation import CloudFormationResourceSummary

LOG = logging.getLogger(__name__)


class RemoteInvokeExecutorFactory:
    def __init__(self, boto_client_provider: Callable[[str], Any]):
        # defining _boto_client_provider causes issues see https://github.com/python/mypy/issues/708
        self._boto_client_provider = boto_client_provider

    def create_remote_invoke_executor(
        self, cfn_resource_summary: CloudFormationResourceSummary
    ) -> Optional[RemoteInvokeExecutor]:
        """
        Creates remote invoker with given CloudFormationResourceSummary

        Parameters
        ----------
        cfn_resource_summary : CloudFormationResourceSummary
            Information about the resource, which RemoteInvokeExecutor will be created for

        Returns:
        -------
        Optional[RemoteInvokeExecutor]
            RemoteInvoker instance for the given CFN resource, None if the resource is not supported yet

        """
        remote_invoke_executor = RemoteInvokeExecutorFactory.REMOTE_INVOKE_EXECUTOR_MAPPING.get(
            cfn_resource_summary.resource_type
        )

        if remote_invoke_executor:
            return remote_invoke_executor(self, cfn_resource_summary)

        LOG.error(
            "Can't find test executor instance for resource %s for type %s",
            cfn_resource_summary.logical_resource_id,
            cfn_resource_summary.resource_type,
        )

        return None

    # mapping definition for each supported resource type
    REMOTE_INVOKE_EXECUTOR_MAPPING: Dict[
        str, Callable[["RemoteInvokeExecutorFactory", CloudFormationResourceSummary], RemoteInvokeExecutor]
    ] = {}
