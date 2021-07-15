"""
Test executor factory to instantiate test executor for given resource
"""
import logging
from typing import Dict, Callable, Any, Optional

from samcli.commands._utils.resources import AWS_LAMBDA_FUNCTION, AWS_SQS_QUEUE
from samcli.lib.test.lambda_test_executor import (
    LambdaConvertToDefaultJSON,
    LambdaResponseConverter,
    LambdaInvokeExecutor,
)
from samcli.lib.test.sqs_test_executor import SqsSendMessageExecutor, SqsConvertToEntriesJsonObject
from samcli.lib.test.test_executors import TestExecutor, ResponseObjectToJsonStringMapper
from samcli.lib.utils.cloudformation import CloudFormationResourceSummary

LOG = logging.getLogger(__name__)


class TestExecutorFactory:
    """
    Factory implementation to instantiate different test executor for different resource types
    """

    def __init__(self, boto_client_provider: Callable[[str], Any]):
        # defining _boto_client_provider causes issues see https://github.com/python/mypy/issues/708
        self._boto_client_provider = boto_client_provider

    def create_test_executor(self, cfn_resource_summary: CloudFormationResourceSummary) -> Optional[TestExecutor]:
        """
        Creates test executor with given CloudFormationResourceSummary

        Parameters
        ----------
        cfn_resource_summary : CloudFormationResourceSummary
            Information about the resource, which TestExecutor will be created for

        Returns:
        -------
        Optional[TestExecutor]
            TestExecutor instance for the given CFN resource, None if the resource is not supported yet

        """
        test_executor = TestExecutorFactory.EXECUTOR_MAPPING.get(cfn_resource_summary.resource_type)

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
            request_mappers=[LambdaConvertToDefaultJSON()],
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

    # mapping definition for each supported resource type
    EXECUTOR_MAPPING: Dict[str, Callable[["TestExecutorFactory", CloudFormationResourceSummary], TestExecutor]] = {
        AWS_LAMBDA_FUNCTION: _create_lambda_test_executor,
        AWS_SQS_QUEUE: _create_sqs_test_executor,
    }
