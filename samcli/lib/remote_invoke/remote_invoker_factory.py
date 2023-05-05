"""
Remote Invoke factory to instantiate remote invoker for given resource
"""
import logging
from typing import Callable, Any, Optional

from samcli.lib.utils.cloudformation import CloudFormationResourceSummary

LOG = logging.getLogger(__name__)

class RemoteInvokerFactory:

    def __init__(self, boto_client_provider: Callable[[str], Any]):
        # defining _boto_client_provider causes issues see https://github.com/python/mypy/issues/708
        self._boto_client_provider = boto_client_provider

    def create_remote_invoker(self, cfn_resource_summary: CloudFormationResourceSummary) -> Optional[RemoteInvoker]:
        """
        Creates remote invoker with given CloudFormationResourceSummary

        Parameters
        ----------
        cfn_resource_summary : CloudFormationResourceSummary
            Information about the resource, which TestExecutor will be created for

        Returns:
        -------
        Optional[RemoteInvoker]
            RemoteInvoker instance for the given CFN resource, None if the resource is not supported yet

        """
        test_executor = RemoteInvokerFactory.EXECUTOR_MAPPING.get(cfn_resource_summary.resource_type)

        if test_executor:
            return test_executor(self, cfn_resource_summary)

        LOG.error(
            "Can't find test executor instance for resource %s for type %s",
            cfn_resource_summary.logical_resource_id,
            cfn_resource_summary.resource_type,
        )

        return None

    def _create_lambda_test_executor(self, cfn_resource_summary: CloudFormationResourceSummary):
        return TestExecutor(
            request_mappers=[DefaultConvertToJSON()],
            response_mappers=[LambdaResponseConverter(), ResponseObjectToJsonStringMapper()],
            boto_action_executor=LambdaInvokeExecutor(
                self._boto_client_provider("lambda"),
                cfn_resource_summary.physical_resource_id,
            ),
        )

    def _create_sqs_test_executor(self, cfn_resource_summary: CloudFormationResourceSummary):
        return TestExecutor(
            request_mappers=[
                SqsConvertToEntriesJsonObject(),
            ],
            response_mappers=[ResponseObjectToJsonStringMapper()],
            boto_action_executor=SqsSendMessageExecutor(
                self._boto_client_provider("sqs"),
                cfn_resource_summary.physical_resource_id,
            ),
        )

    def _create_kinesis_test_executor(self, cfn_resource_summary: CloudFormationResourceSummary):
        return TestExecutor(
            request_mappers=[
                KinesisConvertToRecordsJsonObject(),
            ],
            response_mappers=[ResponseObjectToJsonStringMapper()],
            boto_action_executor=KinesisPutRecordsExecutor(
                self._boto_client_provider("kinesis"),
                cfn_resource_summary.physical_resource_id,
            ),
        )

    def _create_stepfunctions_test_executor(self, cfn_resource_summary: CloudFormationResourceSummary):
        return TestExecutor(
            request_mappers=[
                DefaultConvertToJSON(),
            ],
            response_mappers=[ResponseObjectToJsonStringMapper()],
            boto_action_executor=StepFunctionsStartExecutionExecutor(
                self._boto_client_provider("stepfunctions"),
                cfn_resource_summary.physical_resource_id,
            ),
        )

    # mapping definition for each supported resource type
    INVOKER_MAPPING: Dict[str, Callable[["TestExecutorFactory", CloudFormationResourceSummary], RemoteInvoker]] = {
        AWS_LAMBDA_FUNCTION: _create_lambda_test_executor,
        AWS_SQS_QUEUE: _create_sqs_test_executor,
        AWS_KINESIS_STREAM: _create_kinesis_test_executor,
        AWS_STEPFUNCTIONS_STATEMACHINE: _create_stepfunctions_test_executor,
    }
