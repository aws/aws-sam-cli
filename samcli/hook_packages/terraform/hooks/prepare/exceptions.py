"""
Module containing prepare hook-related exceptions
"""
import os

ONE_LAMBDA_LAYER_LINKING_ISSUE_LINK = "<<TODO: create this issue before the release>>"
LOCAL_VARIABLES_SUPPORT_ISSUE_LINK = "<<TODO: create this issue before the release>>"


class InvalidResourceLinkingException(Exception):
    fmt = "An error occurred when attempting to link two resources: {message}"

    def __init__(self, message):
        msg = self.fmt.format(message=message)
        Exception.__init__(self, msg)


class OneLambdaLayerLinkingLimitationException(Exception):
    fmt = (
        "SAM CLI could not process a Terraform project that contains Lambda functions that are linked to more than one "
        "lambda layer. Layer(s) defined by {layers_list} could not be linked to lambda function {function_id}."
        "{line_sep}Related issue: {issue_link}."
    )

    def __init__(self, layers_list, function_id):
        msg = self.fmt.format(
            layers_list=layers_list,
            function_id=function_id,
            issue_link=ONE_LAMBDA_LAYER_LINKING_ISSUE_LINK,
            line_sep=os.linesep,
        )
        Exception.__init__(self, msg)


class LocalVariablesLinkingLimitationException(Exception):
    fmt = (
        "SAM CLI could not process a Terraform project that uses local variables to define the Lambda functions "
        "layers. Layer(s) defined by {local_variable_reference} could be linked to lambda function {function_id}."
        "{line_sep}Related issue: {issue_link}."
    )

    def __init__(self, local_variable_reference, function_id):
        msg = self.fmt.format(
            local_variable_reference=local_variable_reference,
            function_id=function_id,
            issue_link=LOCAL_VARIABLES_SUPPORT_ISSUE_LINK,
            line_sep=os.linesep,
        )
        Exception.__init__(self, msg)
