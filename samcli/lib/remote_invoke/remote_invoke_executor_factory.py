"""
Remote Invoke factory to instantiate remote invoker for given resource
"""
import logging
from typing import Any, Callable, Dict, Optional

from samcli.lib.remote_invoke.lambda_invoke_executors import (
    DefaultConvertToJSON,
    LambdaInvokeExecutor,
    LambdaInvokeWithResponseStreamExecutor,
    LambdaResponseConverter,
    LambdaStreamResponseConverter,
    _is_function_invoke_mode_response_stream,
)
from samcli.lib.remote_invoke.remote_invoke_executors import (
    RemoteInvokeConsumer,
    RemoteInvokeExecutor,
    RemoteInvokeLogOutput,
    RemoteInvokeOutputFormat,
    RemoteInvokeResponse,
    ResponseObjectToJsonStringMapper,
)
from samcli.lib.remote_invoke.stepfunctions_invoke_executors import (
    SfnDescribeExecutionResponseConverter,
    StepFunctionsStartExecutionExecutor,
)
from samcli.lib.utils.cloudformation import CloudFormationResourceSummary
from samcli.lib.utils.resources import AWS_LAMBDA_FUNCTION

LOG = logging.getLogger(__name__)


class RemoteInvokeExecutorFactory:
    def __init__(self, boto_client_provider: Callable[[str], Any]):
        # defining _boto_client_provider causes issues see https://github.com/python/mypy/issues/708
        self._boto_client_provider = boto_client_provider

    def create_remote_invoke_executor(
        self,
        cfn_resource_summary: CloudFormationResourceSummary,
        output_format: RemoteInvokeOutputFormat,
        response_consumer: RemoteInvokeConsumer[RemoteInvokeResponse],
        log_consumer: RemoteInvokeConsumer[RemoteInvokeLogOutput],
    ) -> Optional[RemoteInvokeExecutor]:
        """
        Creates remote invoker with given CloudFormationResourceSummary

        Parameters
        ----------
        cfn_resource_summary : CloudFormationResourceSummary
            Information about the resource, which RemoteInvokeExecutor will be created for
        output_format: RemoteInvokeOutputFormat
            Output format of the current remote invoke execution, passed down to executor itself
        response_consumer: RemoteInvokeConsumer[RemoteInvokeResponse]
            Consumer instance which can process RemoteInvokeResponse events
        log_consumer: RemoteInvokeConsumer[RemoteInvokeLogOutput]
            Consumer instance which can process RemoteInvokeLogOutput events

        Returns
        -------
        Optional[RemoteInvokeExecutor]
            RemoteInvoker instance for the given CFN resource, None if the resource is not supported yet

        """
        remote_invoke_executor = RemoteInvokeExecutorFactory.REMOTE_INVOKE_EXECUTOR_MAPPING.get(
            cfn_resource_summary.resource_type
        )

        if remote_invoke_executor:
            return remote_invoke_executor(self, cfn_resource_summary, output_format, response_consumer, log_consumer)

        LOG.error(
            "Can't find remote invoke executor instance for resource %s for type %s",
            cfn_resource_summary.logical_resource_id,
            cfn_resource_summary.resource_type,
        )

        return None

    def _create_lambda_boto_executor(
        self,
        cfn_resource_summary: CloudFormationResourceSummary,
        remote_invoke_output_format: RemoteInvokeOutputFormat,
        response_consumer: RemoteInvokeConsumer[RemoteInvokeResponse],
        log_consumer: RemoteInvokeConsumer[RemoteInvokeLogOutput],
    ) -> RemoteInvokeExecutor:
        """Creates a remote invoke executor for Lambda resource type based on
        the boto action being called.

        Parameters
        ----------
        cfn_resource_summary: CloudFormationResourceSummary
            Information about the Lambda resource
        remote_invoke_output_format: RemoteInvokeOutputFormat
            Response output format that will be used for remote invoke execution
        response_consumer: RemoteInvokeConsumer[RemoteInvokeResponse]
            Consumer instance which can process RemoteInvokeResponse events
        log_consumer: RemoteInvokeConsumer[RemoteInvokeLogOutput]
            Consumer instance which can process RemoteInvokeLogOutput events

        Returns
        -------
        RemoteInvokeExecutor
            Returns the Executor created for Lambda
        """
        LOG.info("Invoking Lambda Function %s", cfn_resource_summary.logical_resource_id)
        lambda_client = self._boto_client_provider("lambda")
        mappers = []
        if _is_function_invoke_mode_response_stream(lambda_client, cfn_resource_summary.physical_resource_id):
            LOG.debug("Creating response stream invocator for function %s", cfn_resource_summary.physical_resource_id)

            if remote_invoke_output_format == RemoteInvokeOutputFormat.JSON:
                mappers = [
                    LambdaStreamResponseConverter(),
                    ResponseObjectToJsonStringMapper(),
                ]

            return RemoteInvokeExecutor(
                request_mappers=[DefaultConvertToJSON()],
                response_mappers=mappers,
                boto_action_executor=LambdaInvokeWithResponseStreamExecutor(
                    lambda_client, cfn_resource_summary.physical_resource_id, remote_invoke_output_format
                ),
                response_consumer=response_consumer,
                log_consumer=log_consumer,
            )

        if remote_invoke_output_format == RemoteInvokeOutputFormat.JSON:
            mappers = [
                LambdaResponseConverter(),
                ResponseObjectToJsonStringMapper(),
            ]

        return RemoteInvokeExecutor(
            request_mappers=[DefaultConvertToJSON()],
            response_mappers=mappers,
            boto_action_executor=LambdaInvokeExecutor(
                lambda_client, cfn_resource_summary.physical_resource_id, remote_invoke_output_format
            ),
            response_consumer=response_consumer,
            log_consumer=log_consumer,
        )

    def _create_stepfunctions_boto_executor(
        self,
        cfn_resource_summary: CloudFormationResourceSummary,
        remote_invoke_output_format: RemoteInvokeOutputFormat,
        response_consumer: RemoteInvokeConsumer[RemoteInvokeResponse],
        log_consumer: RemoteInvokeConsumer[RemoteInvokeLogOutput],
    ) -> RemoteInvokeExecutor:
        """Creates a remote invoke executor for Step Functions resource type based on
        the boto action being called.

        Parameters
        ----------
        cfn_resource_summary: CloudFormationResourceSummary
            Information about the Step Function resource
        remote_invoke_output_format: RemoteInvokeOutputFormat
            Response output format that will be used for remote invoke execution
        response_consumer: RemoteInvokeConsumer[RemoteInvokeResponse]
            Consumer instance which can process RemoteInvokeResponse events
        log_consumer: RemoteInvokeConsumer[RemoteInvokeLogOutput]
            Consumer instance which can process RemoteInvokeLogOutput events

        Returns
        -------
        RemoteInvokeExecutor
            Returns the Executor created for Step Functions
        """
        LOG.info("Invoking Step Function %s", cfn_resource_summary.logical_resource_id)
        sfn_client = self._boto_client_provider("stepfunctions")
        mappers = []
        if remote_invoke_output_format == RemoteInvokeOutputFormat.JSON:
            mappers = [
                SfnDescribeExecutionResponseConverter(),
                ResponseObjectToJsonStringMapper(),
            ]
        return RemoteInvokeExecutor(
            request_mappers=[DefaultConvertToJSON()],
            response_mappers=mappers,
            boto_action_executor=StepFunctionsStartExecutionExecutor(
                sfn_client, cfn_resource_summary.physical_resource_id, remote_invoke_output_format
            ),
            response_consumer=response_consumer,
            log_consumer=log_consumer,
        )

    # mapping definition for each supported resource type
    REMOTE_INVOKE_EXECUTOR_MAPPING: Dict[
        str,
        Callable[
            [
                "RemoteInvokeExecutorFactory",
                CloudFormationResourceSummary,
                RemoteInvokeOutputFormat,
                RemoteInvokeConsumer[RemoteInvokeResponse],
                RemoteInvokeConsumer[RemoteInvokeLogOutput],
            ],
            RemoteInvokeExecutor,
        ],
    ] = {AWS_LAMBDA_FUNCTION: _create_lambda_boto_executor}
