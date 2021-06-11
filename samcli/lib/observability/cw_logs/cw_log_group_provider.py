"""
Discover & provide the log group name
"""
from typing import Optional
import logging
import boto3
from samcli.commands._utils.resources import AWS_LAMBDA_FUNCTION, AWS_APIGATEWAY_RESTAPI, AWS_APIGATEWAY_HTTPAPI

LOG = logging.getLogger(__name__)


class LogGroupProvider:
    """
    Resolve the name of log group given the name of the resource
    """

    @staticmethod
    def for_resource(resource_type: str, name: str) -> Optional[str]:
        log_group = None
        if resource_type == AWS_LAMBDA_FUNCTION:
            log_group = LogGroupProvider.for_lambda_function(name)
        elif resource_type == AWS_APIGATEWAY_RESTAPI:
            log_group = LogGroupProvider.for_apigw_rest_api(name)
        elif resource_type == AWS_APIGATEWAY_HTTPAPI:
            log_group = LogGroupProvider.for_apigwv2_http_api(name)

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
    def for_apigwv2_http_api(http_api_id: str, stage: str = "$default") -> Optional[str]:
        """
        Returns the CloudWatch Log Group Name created by default for the AWS Api gatewayv2 http api with given id

        Parameters
        ----------
        http_api_id : str
            Id of the http api
        stage: str
            Stage of the rest api (the default value is "$default")

        Returns
        -------
        str
            Default Log Group name used by this http api
        """
        apigw2_client = boto3.client("apigatewayv2")

        # TODO: A http api may have multiple stage, here just log out the default stage and can be extended to log out
        #  all stages or a specific stage if needed.
        stage_info = apigw2_client.get_stage(ApiId=http_api_id, StageName=stage)
        log_setting = stage_info.get("AccessLogSettings", None)
        if not log_setting:
            LOG.warning("Access logging is disabled for http api id (%s)", http_api_id)
            return None
        log_group_name = str(log_setting.get("DestinationArn").split(":")[-1])
        return log_group_name
