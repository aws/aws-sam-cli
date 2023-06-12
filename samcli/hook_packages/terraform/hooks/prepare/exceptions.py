"""
Module containing prepare hook-related exceptions
"""
import os

from samcli.commands.exceptions import UserException

ONE_LAMBDA_LAYER_LINKING_ISSUE_LINK = "https://github.com/aws/aws-sam-cli/issues/4395"
LOCAL_VARIABLES_SUPPORT_ISSUE_LINK = "https://github.com/aws/aws-sam-cli/issues/4396"

APPLY_WORK_AROUND_MESSAGE = "Run terraform apply to populate these values."


class InvalidResourceLinkingException(UserException):
    fmt = "An error occurred when attempting to link two resources: {message}"

    def __init__(self, message):
        msg = self.fmt.format(message=message)
        UserException.__init__(self, msg)


class ApplyLimitationException(UserException):
    def __init__(self, message):
        fmt = "{message}{line_sep}{line_sep}{apply_work_around}"
        msg = fmt.format(message=message, line_sep=os.linesep, apply_work_around=APPLY_WORK_AROUND_MESSAGE)

        UserException.__init__(self, msg)


class OneResourceLinkingLimitationException(ApplyLimitationException):
    fmt = (
        "AWS SAM CLI could not process a Terraform project that contains a source resource that is linked to more "
        "than one destination resource. Destination resource(s) defined by {dest_resource_list} could not be linked to "
        "source resource {source_resource_id}.{line_sep}Related issue: {issue_link}."
    )

    def __init__(self, dest_resource_list, source_resource_id):
        msg = self.fmt.format(
            dest_resource_list=dest_resource_list,
            source_resource_id=source_resource_id,
            issue_link=ONE_LAMBDA_LAYER_LINKING_ISSUE_LINK,
            line_sep=os.linesep,
        )
        ApplyLimitationException.__init__(self, msg)


class OneLambdaLayerLinkingLimitationException(OneResourceLinkingLimitationException):
    """
    Exception specific for Lambda function linking to more than one layer
    """


class LocalVariablesLinkingLimitationException(ApplyLimitationException):
    fmt = (
        "AWS SAM CLI could not process a Terraform project that uses local variables to define linked resources. "
        "Destination resource(s) defined by {local_variable_reference} could not be linked to destination "
        "resource {dest_resource_list}.{line_sep}Related issue: {issue_link}."
    )

    def __init__(self, local_variable_reference, dest_resource_list):
        msg = self.fmt.format(
            local_variable_reference=local_variable_reference,
            dest_resource_list=dest_resource_list,
            issue_link=LOCAL_VARIABLES_SUPPORT_ISSUE_LINK,
            line_sep=os.linesep,
        )
        ApplyLimitationException.__init__(self, msg)


class FunctionLayerLocalVariablesLinkingLimitationException(LocalVariablesLinkingLimitationException):
    """
    Exception specific for Lambda function linking to a layer defined as a local
    """


class OneGatewayResourceToRestApiLinkingLimitationException(OneResourceLinkingLimitationException):
    """
    Exception specific for Gateway Resource linking to more than one Rest API
    """


class GatewayResourceToGatewayRestApiLocalVariablesLinkingLimitationException(LocalVariablesLinkingLimitationException):
    """
    Exception specific for Gateway Resource linking to Rest API using locals.
    """


class OneRestApiToApiGatewayMethodLinkingLimitationException(OneResourceLinkingLimitationException):
    """
    Exception specific for Gateway Method linking to more than Rest API
    """


class RestApiToApiGatewayMethodLocalVariablesLinkingLimitationException(LocalVariablesLinkingLimitationException):
    """
    Exception specific for Gateway Method linking to Rest API using locals.
    """


class OneGatewayResourceToApiGatewayMethodLinkingLimitationException(OneResourceLinkingLimitationException):
    """
    Exception specific for Gateway Method linking to more than API Gateway Resource
    """


class GatewayResourceToApiGatewayMethodLocalVariablesLinkingLimitationException(
    LocalVariablesLinkingLimitationException
):
    """
    Exception specific for Gateway Method linking to Gateway Resource using locals.
    """


class OneRestApiToApiGatewayStageLinkingLimitationException(OneResourceLinkingLimitationException):
    """
    Exception specific for Gateway Stage linking to more than Rest API
    """


class RestApiToApiGatewayStageLocalVariablesLinkingLimitationException(LocalVariablesLinkingLimitationException):
    """
    Exception specific for Gateway Stage linking to Rest API using locals.
    """


class OneRestApiToApiGatewayIntegrationLinkingLimitationException(OneResourceLinkingLimitationException):
    """
    Exception specific for Gateway Integration linking to more than one Rest API
    """


class RestApiToApiGatewayIntegrationLocalVariablesLinkingLimitationException(LocalVariablesLinkingLimitationException):
    """
    Exception specific for Gateway Integration linking to Rest API using locals.
    """


class OneGatewayResourceToApiGatewayIntegrationLinkingLimitationException(OneResourceLinkingLimitationException):
    """
    Exception specific for Gateway Integration linking to more than one Gateway resource
    """


class GatewayResourceToApiGatewayIntegrationLocalVariablesLinkingLimitationException(
    LocalVariablesLinkingLimitationException
):
    """
    Exception specific for Gateway Integration linking to Gateway Resource using locals.
    """


class OneLambdaFunctionResourceToApiGatewayIntegrationLinkingLimitationException(OneResourceLinkingLimitationException):
    """
    Exception specific for Gateway Integration linking to more than one Lambda function resource
    """


class LambdaFunctionToApiGatewayIntegrationLocalVariablesLinkingLimitationException(
    LocalVariablesLinkingLimitationException
):
    """
    Exception specific for Gateway Integration linking to a Lambda function resource using locals.
    """


class OneRestApiToApiGatewayIntegrationResponseLinkingLimitationException(OneResourceLinkingLimitationException):
    """
    Exception specific for Gateway Integration Response linking to more than one Rest API
    """


class RestApiToApiGatewayIntegrationResponseLocalVariablesLinkingLimitationException(
    LocalVariablesLinkingLimitationException
):
    """
    Exception specific for Gateway Integration Response linking to Rest API using locals.
    """


class OneGatewayResourceToApiGatewayIntegrationResponseLinkingLimitationException(
    OneResourceLinkingLimitationException
):
    """
    Exception specific for Gateway Integration Response linking to more than one Gateway resource
    """


class GatewayResourceToApiGatewayIntegrationResponseLocalVariablesLinkingLimitationException(
    LocalVariablesLinkingLimitationException
):
    """
    Exception specific for Gateway Integration Response linking to Gateway Resource using locals.
    """


class OneGatewayAuthorizerToLambdaFunctionLinkingLimitationException(OneResourceLinkingLimitationException):
    """
    Exception specific for Gateway Authorizer linking to more than one Lambda Function
    """


class GatewayAuthorizerToLambdaFunctionLocalVariablesLinkingLimitationException(
    LocalVariablesLinkingLimitationException
):
    """
    Exception specific for Gateway Authorizer linking to Lambda Function using locals.
    """


class OneGatewayAuthorizerToRestApiLinkingLimitationException(OneResourceLinkingLimitationException):
    """
    Exception specific for Gateway Authorizer linking to more than one Rest API
    """


class GatewayAuthorizerToRestApiLocalVariablesLinkingLimitationException(LocalVariablesLinkingLimitationException):
    """
    Exception specific for Gateway Authorizer linking to Rest APIs using locals.
    """


class OneGatewayMethodToGatewayAuthorizerLinkingLimitationException(OneResourceLinkingLimitationException):
    """
    Exception specific for Gateway Method linking to more than one Gateway Authorizer
    """


class GatewayMethodToGatewayAuthorizerLocalVariablesLinkingLimitationException(
    LocalVariablesLinkingLimitationException
):
    """
    Exception specific for Gateway Method linking to Gateway Authorizer using locals.
    """


class InvalidSamMetadataPropertiesException(UserException):
    pass


class OpenAPIBodyNotSupportedException(ApplyLimitationException):
    fmt = (
        "AWS SAM CLI is unable to process a Terraform project that uses an OpenAPI specification to "
        "define the API Gateway resource. AWS SAM CLI does not currently support this "
        "functionality. Affected resource: {api_id}."
    )

    def __init__(self, api_id):
        msg = self.fmt.format(
            api_id=api_id,
        )
        ApplyLimitationException.__init__(self, msg)
