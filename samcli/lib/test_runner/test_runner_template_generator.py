import re
import logging
import jinja2
from typing import *
from botocore.exceptions import ClientError
from samcli.lib.utils.boto_utils import BotoProviderType

LOG = logging.getLogger(__name__)


def _extract_api_id_from_arn(api_arn: str) -> str:
    """
    Extracts an api id from an HTTP or REST api arn.

    NOTE: https://docs.aws.amazon.com/apigateway/latest/developerguide/arn-format-reference.html

    REST API Arn: `arn:partition:apigateway:region::/restapis/api-id`

    HTTP API Arn: `arn:partition:apigateway:region::/apis/api-id`

    Parameters
    ----------
    api_arn : str
        The arn of the HTTP or REST api from which the api id is extracted.

    Returns
    -------
    str
        The api id from the api arn.
    """

    return api_arn[api_arn.rindex("/") + 1 :]


def _get_permissions_map() -> dict:
    """
    Returns a dictionary mapping a Regular Expression representing the arn of a specific resource
    to the AWS Resource Type and the default permissions generated for that resource.

    Returns
    -------
    default_permissions_map : dict
        A dictionary mapping a Regular Expression representing the arn of a resource to an object
        containing the AWS Resource Type and the list of IAM Action permissions generated for that resource.
    """

    partition_regex = r"(aws|aws-cn|aws-us-gov)"
    region_regex = r"(us(-gov)?|ap|ca|cn|eu|sa)-(central|(north|south)?(east|west)?)-\d"
    account_regex = r"\d{12}"

    default_permissions_map = {
        rf"^arn:{partition_regex}:lambda:{region_regex}:{account_regex}:function:[\w-]+(:\d+)?$": {
            "Resource": "AWS::Lambda::Function",
            "Action": ["lambda:InvokeFunction"],
        },
        rf"^arn:{partition_regex}:apigateway:{region_regex}::\/apis\/\w+$": {
            "Resource": "AWS::ApiGateway::Api",
            "Action": ["execute-api:Invoke"],
        },
        rf"^arn:{partition_regex}:apigateway:{region_regex}::\/restapis\/\w+$": {
            "Resource": "AWS::ApiGateway::RestApi",
            "Action": ["execute-api:Invoke"],
        },
        rf"^arn:{partition_regex}:sqs:{region_regex}:{account_regex}:[\w-]+$": {
            "Resource": "AWS::SQS::Queue",
            "Action": ["sqs:SendMessage"],
        },
        rf"^arn:{partition_regex}:s3:::[\w-]+$": {
            "Resource": "AWS::S3::Bucket",
            "Action": ["s3:PutObject", "s3:GetObject"],
        },
        rf"^arn:{partition_regex}:dynamodb:{region_regex}:{account_regex}:table\/[\w-]+$": {
            "Resource": "AWS::Dynamodb::Table",
            "Action": [
                "dynamodb:GetItem",
                "dynamodb:PutItem",
            ],
        },
        rf"^arn:{partition_regex}:states:{region_regex}:{account_regex}:stateMachine:[\w-]+$": {
            "Resource": "AWS::StepFunctions::StateMachine",
            "Action": [
                "stepfunction:StartExecution",
                "stepfunction:StopExecution",
            ],
        },
    }
    return default_permissions_map


def _get_action_mapping(resource_arn: str) -> Union[dict, None]:

    """
    Returns a dictionary mapping a Resource type to a list of IAM actions generated for that resource.

    Returns `None` if the supplied ARN is for a Resource type without any IAM actions supported.

    Parameters
    ----------
    resource_arn:
        The arn of the resource for which the mapping is returned.

    Returns
    -------
    dict:
        A dictionary containing two keys: `'Resource'` and `'Action'`. `'Resource'` contains the AWS Resource for which the IAM actions list contained in `'Action'` maps to.

        For example `{"Resource": "AWS::S3::Bucket", "Action": ["s3:PutObject", "s3:GetObject"]}`

    """

    permissions_map = _get_permissions_map()

    for arn_regex, mapping in permissions_map.items():
        if re.search(arn_regex, resource_arn) is not None:
            LOG.info("Matched ARN `%s` to IAM actions %s", resource_arn, mapping["Action"])
            return mapping

    # If the supplied ARN is for a resource without any default actions supported
    LOG.info("Found no match for ARN `%s` to any IAM actions.", resource_arn)
    return None


def _create_iam_statment_string(resource_arn: str) -> str:
    """
    Returns an IAM Statement in the form of a YAML string corresponding to the supplied resource ARN.

    The generated Actions are commented out to establish a barrier of consent, preventing customers from accidentally granting permissions that they did not mean to.

    The Action list is empty if there are no IAM Action permissions to generate for the given resource.

    Parameters
    ----------
    resource_arn : str
        The arn of the resource for which the IAM statement is generated.

    Returns
    -------
    str:
        An IAM Statement in the form of a YAML string.
    """

    # NOTE: The spacing within these strings is needed to keep the resulting YAML indentation valid
    new_statement_template = (
        "- Effect: Allow\n"
        "  Action:\n"
        "   {%- for action in action_list %}\n"
        "     # - {{action}}\n"
        "   {%- endfor %}\n"
        "  Resource: {{arn}}\n"
    )
    mapping = _get_action_mapping(resource_arn)

    if mapping is None:
        return jinja2.Template(source=new_statement_template, keep_trailing_newline=True).render(
            action_list=[], arn=resource_arn
        )

    if mapping["Resource"] in ("AWS::ApiGateway::Api", "AWS::ApiGateway::RestApi"):
        apiId = _extract_api_id_from_arn(resource_arn)
        execute_api_arn = (
            f"!Sub arn:${{AWS::Partition}}:execute-api:${{AWS::Region}}:${{AWS::AccountId}}:{apiId}/*/GET/*"
        )
        return jinja2.Template(source=new_statement_template, keep_trailing_newline=True).render(
            action_list=mapping["Action"], arn=execute_api_arn
        )

    return jinja2.Template(source=new_statement_template, keep_trailing_newline=True).render(
        action_list=mapping["Action"], arn=resource_arn
    )


def _query_tagging_api(tag_filters: dict, boto_client_provider: BotoProviderType) -> Union[dict, None]:
    """
    Queries the Tagging API to retrieve the ARNs of every resource with the given tags.

    NOTE: https://docs.aws.amazon.com/cli/latest/reference/resourcegroupstaggingapi/get-resources.html#get-resources

    Parameters
    ----------
    tag_filters : dict
        The tag filters to restrict output to only those resources with the given tags.

        NOTE: https://docs.aws.amazon.com/cli/latest/reference/resourcegroupstaggingapi/get-resources.html#options

    boto_client_provider : BotoProviderType
        Provides a boto3 client in order to query tagging API

    Returns
    -------
    dict
        A ResourceTagMappingList, which contains a list of resource ARNs and tags associated with each.

        NOTE: https://docs.aws.amazon.com/cli/latest/reference/resourcegroupstaggingapi/get-resources.html#output

    Throws
    ------
    botocore.ClientError
        If the `get_resources` call fails.

        See # https://boto3.amazonaws.com/v1/documentation/api/latest/guide/error-handling.html#parsing-error-responses-and-catching-exceptions-from-aws-services
    """
    return boto_client_provider("resourcegroupstaggingapi").get_resources(TagFilters=tag_filters)[
        "ResourceTagMappingList"
    ]


def _generate_statement_string(tag_filters: dict, boto_client_provider: BotoProviderType) -> Union[str, None]:
    """
    Generates a list of IAM statements in the form of a single YAML string with default action permissions for resources with the given tags.

    Returns a YAML comment error message if no resources match the tag, returns None if the tagging api call fails.

    Parameters
    ----------
    tag_filters : dict
        The tag filters to restrict output to only those resources with the given tags.

        NOTE: https://docs.aws.amazon.com/cli/latest/reference/resourcegroupstaggingapi/get-resources.html#options

    boto_client_provider : BotoProviderType
        Provides a boto3 client in order to query tagging API

    Returns
    -------
    str:
        The list of IAM statements in the form of a single YAML string corresponding to the resources specified by the given tags.

        Returns a YAML comment error message if no resources match the tag, returns None if the tagging api call fails.
    """
    resource_tag_mapping_list = _query_tagging_api(tag_filters, boto_client_provider)

    if len(resource_tag_mapping_list) == 0:
        raise KeyError("No resources match the tag: %s, cannot generate any IAM permissions.", str(tag_filters))

    iam_statements = [_create_iam_statment_string(resource["ResourceARN"]) for resource in resource_tag_mapping_list]
    return "".join(iam_statements)


def generate_test_runner_template_string(
    boto_client_provider: BotoProviderType,
    jinja_base_template: str,
    s3_bucket_name: str,
    image_uri: str,
    tag_filters: dict,
) -> Union[dict, None]:
    """
    Renders a base jinja template with a set of parameters needed to create the Test Runner Stack.

    Parameters
    ----------

    boto_client_provider : BotoProviderType
        Provides a boto3 client in order to query tagging API
        
    jinja_base_template : str
        The jinja YAML template to which parameters are substituted.

    s3_bucket_name : str
        The name of the S3 bucket used by the Test Runner Stack.

    image_uri : str
        The URI of the Image to be used by the Test Runner Fargate task definition.

    tag_filters : dict
        The tag filters to restrict generating default IAM action permissions to those resources with the given tags.

        NOTE: https://docs.aws.amazon.com/cli/latest/reference/resourcegroupstaggingapi/get-resources.html#options

    Returns
    -------
    dict
        The Test Runner CloudFormation template in the form of a YAML string.

    """

    try:
        generated_statements = _generate_statement_string(tag_filters, boto_client_provider)
    # https://boto3.amazonaws.com/v1/documentation/api/latest/guide/error-handling.html#parsing-error-responses-and-catching-exceptions-from-aws-services
    except ClientError as client_error:
        LOG.exception(
            "Failed to query tagging API. Error code: %s, Message: %s",
            client_error.response["Error"]["Code"],
            client_error.response["Error"]["Message"],
        )
        return None
    except KeyError as value_error:
        LOG.exception(value_error)
        return None

    data = {"image_uri": image_uri, "s3_bucket_name": s3_bucket_name, "generated_statements": generated_statements}

    try:
        return jinja2.Template(jinja_base_template, undefined=jinja2.StrictUndefined).render(data)
    except jinja2.exceptions.TemplateError as template_error:
        LOG.exception("Failed to render jinja template: %s", template_error)
        return None
