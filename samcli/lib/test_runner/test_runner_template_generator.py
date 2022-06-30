import json
import boto3
import re
import logging
from jinja2 import Template
from cfn_flip import to_yaml
from typing import *

LOG = logging.getLogger(__name__)


def __extract_api_id_from_arn(api_arn: str) -> str:
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


def __get_permissions_map() -> dict:
    """
    Returns a dictionary mapping a Regular Expression representing the arn of a specific resource to the default permissions generated for that resource.

    Returns
    -------
    default_permissions_map : dict
        A dictionary mapping a Regular Expression representing the arn of a resource to a list of IAM Action permissions generated for that resource.
    """

    partition_ex = "(aws|aws-cn|aws-us-gov)"
    region_ex = "\w+-\w+-\d"
    account_ex = "\d{12}"

    default_permissions_map = {
        # AWS::Lambda::Function
        rf"^arn:{partition_ex}:lambda:{region_ex}:{account_ex}:function:[\w-]+(:\d+)?$": ["lambda:InvokeFunction"],
        # AWS::ApiGateway::Api
        rf"^arn:{partition_ex}:apigateway:{region_ex}::\/apis\/\w+$": ["execute-api:Invoke"],
        # AWS::ApiGateway::RestApi
        rf"^arn:{partition_ex}:apigateway:{region_ex}::\/restapis\/\w+$": ["execute-api:Invoke"],
        # AWS::SQS::Queue
        rf"^arn:{partition_ex}:sqs:{region_ex}:{account_ex}:[\w-]+$": ["sqs:SendMessage"],
        # AWS::S3::Bucket
        rf"^arn:{partition_ex}:s3:::[\w-]+$": ["s3:PutObject", "s3:GetObject"],
        # AWS::Dynamodb::Table
        rf"^arn:{partition_ex}:dynamodb:{region_ex}:{account_ex}:table\/[\w-]+$": [
            "dynamodb:GetItem",
            "dynamodb:PutItem",
        ],
        # AWS::StepFunctions::StateMachine
        rf"^arn:{partition_ex}:states:{region_ex}:{account_ex}:stateMachine:[\w-]+$": [
            "stepfunction:StartExecution",
            "stepfunction:StopExecution",
        ],
    }
    return default_permissions_map


def __get_permissions(resource_arn: str) -> List[str]:
    """
    Returns a list of IAM Action permissions to generate given a resource arn.

    An empty list is returned if there are no IAM Action permissions to generate for the given resource.

    Parameters
    ----------
    resource_arn : str
        The arn of the resource for which IAM Action permissions are returned.

    Returns
    -------
    List[str]
        The list of IAM Action permissions to generate for a given resource.
    """

    permissions_map = __get_permissions_map()

    for arnExp in permissions_map.keys():
        if re.search(arnExp, resource_arn) is not None:
            LOG.info("Matched ARN `%s` to IAM actions %s", resource_arn, str(permissions_map[arnExp]))
            return permissions_map[arnExp]
    LOG.info("No IAM actions supported for ARN `%s`", resource_arn)
    return []


def __generate_base_test_runner_template_json(
    jinja_template_json_string: str,
    bucket_name: str,
    ecs_task_exec_role_arn: str,
    image_uri: str,
    vpc_id: str,
    cpu: int,
    memory: int,
) -> dict:
    """
    Renders a base jinja template with a set of parameters needed to create the Test Runner Stack.

    Parameters
    ----------
    jinja_template_json_string : str
        The base jinja template to which parameters are substituted.

    bucket_name : str
        The name of the S3 bucket used by the Test Runner Stack.

    ecs_task_exec_role_arn : str
        The ARN of the AWS ECS Task Execution Role used by the Test Runner Stack.

        NOTE: https://docs.aws.amazon.com/AmazonECS/latest/developerguide/task_execution_IAM_role.html

    image_uri : str
        The URI of the Image to be used by the Test Runner Fargate task definition.

    vpc_id : str
        The ID of the VPC associated with the Test Runner security group.

        NOTE: The security group (and associated VPC) is required to invoke the runTask API and run tests

    cpu : int
        The CPU used by the Test Runner Task Definition.

        NOTE: https://docs.aws.amazon.com/AmazonECS/latest/developerguide/task_definition_parameters.html#task_size

    memory : int
        The memory used by the Test Runner Task Definition.

        NOTE: https://docs.aws.amazon.com/AmazonECS/latest/developerguide/task_definition_parameters.html#task_sizes

    Returns
    -------
    dict
        A JSON object representing the CloudFormation Template for the Test Runner Stack with all parameters substituted in.

    """
    data = {
        "cpu": cpu,
        "memory": memory,
        "vpc_id": vpc_id,
        "ecs_task_exec_role_arn": ecs_task_exec_role_arn,
        "image_uri": image_uri,
        "s3_bucket_name": bucket_name,
    }

    try:
        rendered_template_string = Template(jinja_template_json_string).render(data)
        return json.loads(rendered_template_string)
    except Exception as render_error:
        LOG.exception("Failed to render jinja template: %s", render_error)
        return None


def __query_tagging_api(tag_filters: dict) -> dict:
    """
    Queries the Tagging API to retrieve the ARNs of every resource with the given tags.

    NOTE: https://docs.aws.amazon.com/cli/latest/reference/resourcegroupstaggingapi/get-resources.html#get-resources

    Parameters
    ----------
    tag_filters : dict
        The tag filters to restrict output to only those resources with the given tags.

        NOTE: https://docs.aws.amazon.com/cli/latest/reference/resourcegroupstaggingapi/get-resources.html#options

    Returns
    -------
    dict
        A response object containing ResourceTagMappingList, which contains a list of resource ARNs and tags associated with each.

        NOTE: https://docs.aws.amazon.com/cli/latest/reference/resourcegroupstaggingapi/get-resources.html#output


    """
    try:
        return boto3.client("resourcegroupstaggingapi").get_resources(tag_filters=tag_filters)
    except Exception as query_error:
        LOG.error("Failed to call get_resources from resource group tagging api: %s", query_error)
        return None


def __generate_statement_list(tag_filters: dict) -> List[dict]:
    """
    Generates a list of IAM statements with default action permissions for resources with the given tags.

    Parameters
    ----------
    tag_filters : dict
        The tag filters to restrict output to only those resources with the given tags.

        NOTE: https://docs.aws.amazon.com/cli/latest/reference/resourcegroupstaggingapi/get-resources.html#options

    Returns
    -------
    List[dict]
        The list of JSON objects representing IAM statements corresponding to the resources specified by the given tags.
    """

    tagging_api_response = __query_tagging_api(tag_filters)

    if tagging_api_response is None:
        LOG.error("Failed to receive get_resources response, cannot generate any IAM statements.")
        return []

    iam_statements = []

    for resource in tagging_api_response["ResourceTagMappingList"]:
        new_statement = {
            "Effect": "Allow",
            "Action": [],
            "Resource": "",
        }
        arn = resource["ResourceARN"]

        new_statement["Action"].extend(
            # Default permissions are commented out
            ["# " + action for action in __get_permissions(arn)]
        )

        # https://docs.aws.amazon.com/apigateway/latest/developerguide/api-gateway-control-access-using-iam-policies-to-invoke-api.html
        if "# execute-api:Invoke" in new_statement["Action"]:
            apiId = __extract_api_id_from_arn(arn)
            new_statement[
                "Resource"
            ] = f"!Sub arn:${{AWS::Partition}}:execute-api:${{AWS::Region}}:${{AWS::AccountId}}:{apiId}/<STAGE>/GET/<RESOURCE_PATH>"
        else:
            new_statement["Resource"] = arn

        iam_statements.append(new_statement)
    return iam_statements


def __comment_out_default_actions(raw_yaml_string: str) -> str:
    """
    Formats the given YAML string to remove quotes and move `#` to the other side of the list item `-`.

    This is to allow default permissions to actually be commented out.
    This string replacement will produce deterministic results, since the `raw_yaml_string` is deterministic.
    There will be no other instances of `- # ` other than the ones created during the template generation process.

    The purpose is to establish a barrier of consent, to prevent customers from accidentally granting permissions that they did not mean to.

    e.g.

        `- '# lambda:InvokeFunction'` => `# - lambda:InvokeFunction`
    """
    # Move comment hashtag to be in front of list items so they're properly commented out
    return raw_yaml_string.replace("'", "").replace("- # ", "# - ")


def generate_test_runner_string(
    jinja_template_json_string: str,
    bucket_name: str,
    ecs_task_exec_role_arn: str,
    image_uri: str,
    vpc_id: str,
    tag_filters: dict,
    cpu: int = 256,
    memory: int = 512,
) -> str:

    """
    Generates a Test Runner CloudFormation Template based on a base jinja template and given parameters.

    Parameters
    ----------
    jinja_template_json_string : str
        The base jinja template to which parameters are substituted.

    bucket_name : str
        The name of the S3 bucket used by the Test Runner Stack.

    ecs_task_exec_role_arn : str
        The ARN of the AWS ECS Task Execution Role used by the Test Runner Stack.

        NOTE: https://docs.aws.amazon.com/AmazonECS/latest/developerguide/task_execution_IAM_role.html

    image_uri : str
        The URI of the Image to be used by the Test Runner Fargate task definition.

    vpc_id : str
        The ID of the VPC associated with the Test Runner security group.

        NOTE: The security group (and associated VPC) is required to invoke the runTask API and run tests.

    cpu : int
        The CPU used by the Test Runner Task Definition. (DEFAULT = 256)

        NOTE: https://docs.aws.amazon.com/AmazonECS/latest/developerguide/task_definition_parameters.html#task_size

    memory : int
        The memory used by the Test Runner Task Definition. (DEFAULT = 512)

        NOTE: https://docs.aws.amazon.com/AmazonECS/latest/developerguide/task_definition_parameters.html#task_sizes

    tag_filters : dict
        The tag filters to restrict generating default IAM action permissions to those resources with the given tags.

        NOTE: https://docs.aws.amazon.com/cli/latest/reference/resourcegroupstaggingapi/get-resources.html#options

    Returns
    -------
    str
        A YAML string representing a complete Test Runner CloudFormation Template

    """

    test_runner_template = __generate_base_test_runner_template_json(
        jinja_template_json_string,
        bucket_name,
        ecs_task_exec_role_arn,
        image_uri,
        vpc_id,
        cpu,
        memory,
    )
    if test_runner_template is None:
        LOG.exception("Failed to receive base template, aborting template generation.")
        return None

    iam_statements = __generate_statement_list(tag_filters)

    # Attach the generated IAM statements to the Container IAM Role
    test_runner_template["Resources"]["ContainerIAMRole"]["Properties"]["Policies"][0]["PolicyDocument"][
        "Statement"
    ].extend(iam_statements)

    raw_yaml_template_string = to_yaml(json.dumps(test_runner_template))

    processed_yaml_template_string = __comment_out_default_actions(raw_yaml_template_string)

    return processed_yaml_template_string
