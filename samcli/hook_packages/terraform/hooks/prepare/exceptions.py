"""
Module containing prepare hook-related exceptions
"""
import os

from samcli.commands.exceptions import UserException

ONE_LAMBDA_LAYER_LINKING_ISSUE_LINK = "https://github.com/aws/aws-sam-cli/issues/4395"
LOCAL_VARIABLES_SUPPORT_ISSUE_LINK = "https://github.com/aws/aws-sam-cli/issues/4396"


class InvalidResourceLinkingException(UserException):
    fmt = "An error occurred when attempting to link two resources: {message}"

    def __init__(self, message):
        msg = self.fmt.format(message=message)
        UserException.__init__(self, msg)


class OneLambdaLayerLinkingLimitationException(UserException):
    fmt = (
        "AWS SAM CLI could not process a Terraform project that contains Lambda functions that are linked to more "
        "than one lambda layer. Layer(s) defined by {layers_list} could not be linked to lambda function {function_id}."
        "{line_sep}Related issue: {issue_link}."
    )

    def __init__(self, layers_list, function_id):
        msg = self.fmt.format(
            layers_list=layers_list,
            function_id=function_id,
            issue_link=ONE_LAMBDA_LAYER_LINKING_ISSUE_LINK,
            line_sep=os.linesep,
        )
        UserException.__init__(self, msg)


class LocalVariablesLinkingLimitationException(UserException):
    fmt = (
        "AWS SAM CLI could not process a Terraform project that uses local variables to define the Lambda functions "
        "layers. Layer(s) defined by {local_variable_reference} could not be linked to lambda function {function_id}."
        "{line_sep}Related issue: {issue_link}."
    )

    def __init__(self, local_variable_reference, function_id):
        msg = self.fmt.format(
            local_variable_reference=local_variable_reference,
            function_id=function_id,
            issue_link=LOCAL_VARIABLES_SUPPORT_ISSUE_LINK,
            line_sep=os.linesep,
        )
        UserException.__init__(self, msg)


class InvalidSamMetadataPropertiesException(UserException):
    pass
