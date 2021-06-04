"""
Discover & provide the log group name
"""
from typing import Optional

from samcli.commands._utils.resources import AWS_LAMBDA_FUNCTION


class LogGroupProvider:
    """
    Resolve the name of log group given the name of the resource
    """

    @staticmethod
    def for_resource(resource_type: str, name: str) -> Optional[str]:
        if resource_type == AWS_LAMBDA_FUNCTION:
            return LogGroupProvider.for_lambda_function(name)
        return None

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
