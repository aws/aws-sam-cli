"""
Discover & provide the log group name
"""
import logging
from typing import Optional

from samcli.lib.utils.boto_utils import BotoProviderType
from samcli.lib.utils.resources import (
    AWS_APIGATEWAY_RESTAPI,
    AWS_APIGATEWAY_V2_API,
    AWS_LAMBDA_FUNCTION,
    AWS_STEPFUNCTIONS_STATEMACHINE,
)

LOG = logging.getLogger(__name__)


class LogGroupProvider:
    """
    Resolve the name of log group given the name of the resource
    """

    @staticmethod
    def for_resource(boto_client_provider: BotoProviderType, resource_type: str, name: str) -> Optional[str]:
        log_group = None
        if resource_type == AWS_LAMBDA_FUNCTION:
            log_group = LogGroupProvider.for_lambda_function(name)
        elif resource_type == AWS_APIGATEWAY_RESTAPI:
            log_group = LogGroupProvider.for_apigw_rest_api(name)
        elif resource_type == AWS_APIGATEWAY_V2_API:
            log_group = LogGroupProvider.for_apigwv2_http_api(boto_client_provider, name)
        elif resource_type == AWS_STEPFUNCTIONS_STATEMACHINE:
            log_group = LogGroupProvider.for_step_functions(boto_client_provider, name)

        return log_group

    @staticmethod
    def for_lambda_function(function_name: str) -> str:
        """
        Returns the CloudWatch Log Group Name created by default for the AWS Lambda function with given name

        Parameters
        ----------
        function_name : str
            Name of the Lambda function

        Returns
        -------
        str
            Default Log Group name used by this function
        """
        return "/aws/lambda/{}".format(function_name)

    @staticmethod
    def for_apigw_rest_api(rest_api_id: str, stage: str = "Prod") -> str:
        """
        Returns the CloudWatch Log Group Name created by default for the AWS Api gateway rest api with given id

        Parameters
        ----------
        rest_api_id : str
            Id of the rest api
        stage: str
            Stage of the rest api (the default value is "Prod")

        Returns
        -------
        str
            Default Log Group name used by this rest api
        """

        # TODO: A rest api may have multiple stage, here just log out the prod stage and can be extended to log out
        #  all stages or a specific stage if needed.
        return "API-Gateway-Execution-Logs_{}/{}".format(rest_api_id, stage)

    @staticmethod
    def for_apigwv2_http_api(
        boto_client_provider: BotoProviderType, http_api_id: str, stage: str = "$default"
    ) -> Optional[str]:
        """
        Returns the CloudWatch Log Group Name created by default for the AWS Api gatewayv2 http api with given id

        Parameters
        ----------
        boto_client_provider: BotoProviderType
            Boto client provider which contains region and other configurations
        http_api_id : str
            Id of the http api
        stage: str
            Stage of the rest api (the default value is "$default")

        Returns
        -------
        str
            Default Log Group name used by this http api
        """
        apigw2_client = boto_client_provider("apigatewayv2")

        # TODO: A http api may have multiple stage, here just log out the default stage and can be extended to log out
        #  all stages or a specific stage if needed.
        stage_info = apigw2_client.get_stage(ApiId=http_api_id, StageName=stage)
        log_setting = stage_info.get("AccessLogSettings", None)
        if not log_setting:
            LOG.warning("Access logging is disabled for HTTP API ID (%s)", http_api_id)
            return None
        log_group_name = str(log_setting.get("DestinationArn").split(":")[-1])
        return log_group_name

    @staticmethod
    def for_step_functions(
        boto_client_provider: BotoProviderType,
        step_function_name: str,
    ) -> Optional[str]:
        """
        Calls describe_state_machine API to get details of the State Machine,
        then extracts logging information to find the configured CW log group.
        If nothing is configured it will return None

        Parameters
        ----------
        boto_client_provider : BotoProviderType
            Boto client provider which contains region and other configurations
        step_function_name : str
            Name of the step functions resource

        Returns
        -------
            CW log group name if logging is configured, None otherwise
        """
        sfn_client = boto_client_provider("stepfunctions")

        state_machine_info = sfn_client.describe_state_machine(stateMachineArn=step_function_name)
        LOG.debug("State machine info: %s", state_machine_info)

        logging_destinations = state_machine_info.get("loggingConfiguration", {}).get("destinations", [])
        LOG.debug("State Machine logging destinations: %s", logging_destinations)

        # users may configure multiple log groups to send state machine logs, find one and return it
        for logging_destination in logging_destinations:
            log_group_arn = logging_destination.get("cloudWatchLogsLogGroup", {}).get("logGroupArn")
            LOG.debug("Log group ARN: %s", log_group_arn)
            if log_group_arn:
                log_group_index_in_arn = 6
                if ":" in log_group_arn and len(log_group_arn.split(":")) > log_group_index_in_arn:
                    log_group_arn_parts = log_group_arn.split(":")
                    log_group_name = log_group_arn_parts[log_group_index_in_arn]
                    return str(log_group_name)

                LOG.warning(
                    "Invalid Logging configuration for StepFunction %s. Expected ARN but got %s, please check "
                    "your template that you are using ARN of the Cloudwatch LogGroup",
                    step_function_name,
                    log_group_arn,
                )
        LOG.warning("Logging is not configured for StepFunctions (%s)", step_function_name)

        return None
