

class LogGroupProvider(object):
    """
    Resolve the name of log group given the name of the resource
    """

    @staticmethod
    def for_lambda_function(function_name):
        return "/aws/lambda/{}".format(function_name)
