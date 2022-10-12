"""
Module containing prepare hook-related exceptions
"""


class InvalidResourceLinkingException(Exception):
    fmt = "An error occurred when attempting to link two resources: {message}"

    def __init__(self, message):
        msg = self.fmt.format(message=message)
        Exception.__init__(self, msg)


class OneLambdaLayerLinkingLimitationException(Exception):
    fmt = (
        "Sorry, the current version of SAM CLI could not process a Terraform project that contains Lambda functions "
        "that are linked to more than one lambda layer. Layer(s) defined by {layers_list} could not be linked to "
        "lambda function {function_id}"
    )

    def __init__(self, layers_list, function_id):
        msg = self.fmt.format(layers_list=layers_list, function_id=function_id)
        Exception.__init__(self, msg)


class LocalVariablesLinkingLimitationException(Exception):
    fmt = (
        "Sorry, the current version of SAM CLI could not process a Terraform project that uses local variables to "
        "define the Lambda functions layers. Layer(s) defined by {local_variable_reference} could be linked to lambda "
        "function {function_id}"
    )

    def __init__(self, local_variable_reference, function_id):
        msg = self.fmt.format(local_variable_reference=local_variable_reference, function_id=function_id)
        Exception.__init__(self, msg)
