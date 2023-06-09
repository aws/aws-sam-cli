"""
Remote Invoke factory to instantiate remote invoker for given resource
"""
import logging
from typing import Any, Callable, Dict, Optional

from botocore.exceptions import ClientError

from samcli.lib.remote_invoke.lambda_invoke_executors import (
    DefaultConvertToJSON,
    LambdaInvokeExecutor,
    LambdaInvokeWithResponseStreamExecutor,
    LambdaResponseConverter,
    LambdaResponseOutputFormatter,
    LambdaStreamResponseConverter,
    LambdaStreamResponseOutputFormatter,
)
from samcli.lib.remote_invoke.remote_invoke_executors import RemoteInvokeExecutor, ResponseObjectToJsonStringMapper
from samcli.lib.utils.cloudformation import CloudFormationResourceSummary
from samcli.lib.utils.resources import (
    AWS_LAMBDA_FUNCTION,
)

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
            "Can't find remote invoke executor instance for resource %s for type %s",
            cfn_resource_summary.logical_resource_id,
            cfn_resource_summary.resource_type,
        )

        return None

    def _create_lambda_boto_executor(self, cfn_resource_summary: CloudFormationResourceSummary) -> RemoteInvokeExecutor:
        """Creates a remote invoke executor for Lambda resource type based on
        the boto action being called.

        :param cfn_resource_summary: Information about the Lambda resource

        :return: Returns the created remote invoke Executor
        """
        lambda_client = self._boto_client_provider("lambda")
        if _is_function_invoke_mode_response_stream(lambda_client, cfn_resource_summary.physical_resource_id):
            LOG.debug("Creating response stream invocator for function %s", cfn_resource_summary.physical_resource_id)
            return RemoteInvokeExecutor(
                request_mappers=[DefaultConvertToJSON()],
                response_mappers=[
                    LambdaStreamResponseConverter(),
                    LambdaStreamResponseOutputFormatter(),
                    ResponseObjectToJsonStringMapper(),
                ],
                boto_action_executor=LambdaInvokeWithResponseStreamExecutor(
                    lambda_client,
                    cfn_resource_summary.physical_resource_id,
                ),
            )

        return RemoteInvokeExecutor(
            request_mappers=[DefaultConvertToJSON()],
            response_mappers=[
                LambdaResponseConverter(),
                LambdaResponseOutputFormatter(),
                ResponseObjectToJsonStringMapper(),
            ],
            boto_action_executor=LambdaInvokeExecutor(
                lambda_client,
                cfn_resource_summary.physical_resource_id,
            ),
        )

    # mapping definition for each supported resource type
    REMOTE_INVOKE_EXECUTOR_MAPPING: Dict[
        str, Callable[["RemoteInvokeExecutorFactory", CloudFormationResourceSummary], RemoteInvokeExecutor]
    ] = {
        AWS_LAMBDA_FUNCTION: _create_lambda_boto_executor,
    }


def _is_function_invoke_mode_response_stream(lambda_client: Any, function_name: str):
    """
    Returns True if given function has RESPONSE_STREAM as InvokeMode, False otherwise
    """
    try:
        function_url_config = lambda_client.get_function_url_config(FunctionName=function_name)
        function_invoke_mode = function_url_config.get("InvokeMode")
        LOG.debug("InvokeMode of function %s: %s", function_name, function_invoke_mode)
        return function_invoke_mode == "RESPONSE_STREAM"
    except ClientError as ex:
        LOG.debug("Function %s, doesn't have Function URL configured, using regular invoke", function_name, exc_info=ex)
        return False
