"""
Discover & provide the log group name
"""


class LogGroupProvider:
    """
    Resolve the name of log group given the name of the resource
    """

    @staticmethod
    def for_lambda_function(function_name):
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
