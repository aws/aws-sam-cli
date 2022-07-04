import json
import boto3
import re
import logging
from jinja2 import Template
from cfn_flip import to_yaml
from typing import *

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
    Returns a dictionary mapping a Regular Expression representing the arn of a specific resource to the AWS Resource Type and the default permissions generated for that resource.

    Returns
    -------
    default_permissions_map : dict
        A dictionary mapping a Regular Expression representing the arn of a resource to an object containing the AWS Resource Type and the list of IAM Action permissions generated for that resource.
    """

    partition_ex = r"(aws|aws-cn|aws-us-gov)"
    region_ex = r"(us(-gov)?|ap|ca|cn|eu|sa)-(central|(north|south)?(east|west)?)-\d"
    account_ex = r"\d{12}"

    default_permissions_map = {
        rf"^arn:{partition_ex}:lambda:{region_ex}:{account_ex}:function:[\w-]+(:\d+)?$": {
            "Resource": "AWS::Lambda::Function",
            "Action": ["lambda:InvokeFunction"],
        },
        rf"^arn:{partition_ex}:apigateway:{region_ex}::\/apis\/\w+$": {
            "Resource": "AWS::ApiGateway::Api",
            "Action": ["execute-api:Invoke"],
        },
        rf"^arn:{partition_ex}:apigateway:{region_ex}::\/restapis\/\w+$": {
            "Resource": "AWS::ApiGateway::RestApi",
            "Action": ["execute-api:Invoke"],
        },
        rf"^arn:{partition_ex}:sqs:{region_ex}:{account_ex}:[\w-]+$": {
            "Resource": "AWS::SQS::Queue",
            "Action": ["sqs:SendMessage"],
        },
        rf"^arn:{partition_ex}:s3:::[\w-]+$": {
            "Resource": "AWS::S3::Bucket",
            "Action": ["s3:PutObject", "s3:GetObject"],
        },
        rf"^arn:{partition_ex}:dynamodb:{region_ex}:{account_ex}:table\/[\w-]+$": {
            "Resource": "AWS::Dynamodb::Table",
            "Action": [
                "dynamodb:GetItem",
                "dynamodb:PutItem",
            ],
        },
        rf"^arn:{partition_ex}:states:{region_ex}:{account_ex}:stateMachine:[\w-]+$": {
            "Resource": "AWS::StepFunctions::StateMachine",
            "Action": [
                "stepfunction:StartExecution",
                "stepfunction:StopExecution",
            ],
        },
    }
    return default_permissions_map


def _create_iam_statment(resource_arn: str) -> List[str]:
    """
    Returns an IAM Statement corresponding to the supplied resource ARN.

    The Action list is empty if there are no IAM Action permissions to generate for the given resource.

    Parameters
    ----------
    resource_arn : str
        The arn of the resource for which IAM Action permissions are returned.

    Returns
    -------
    List[str]
        The list of IAM Action permissions to generate for a given resource.
    """

    permissions_map = _get_permissions_map()

    new_statement = {
        "Effect": "Allow",
        "Action": [],
        "Resource": resource_arn,
    }

    for arn_exp, mapping in permissions_map.items():
        if re.search(arn_exp, resource_arn) is not None:
            LOG.info("Matched ARN `%s` to IAM actions %s", resource_arn, mapping["Action"])
            # Mark generated actions to be commented out
            new_statement["Action"] = ["# " + action for action in mapping["Action"]]

            # https://docs.aws.amazon.com/apigateway/latest/developerguide/api-gateway-control-access-using-iam-policies-to-invoke-api.html
            if mapping["Resource"] in ("AWS::ApiGateway::Api", "AWS::ApiGateway::RestApi"):
                apiId = _extract_api_id_from_arn(resource_arn)
                new_statement[
                    "Resource"
                ] = f"!Sub arn:${{AWS::Partition}}:execute-api:${{AWS::Region}}:${{AWS::AccountId}}:{apiId}/<STAGE>/GET/<RESOURCE_PATH>"

    return new_statement


def _generate_base_test_runner_template_json(
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


def _query_tagging_api(tag_filters: dict) -> dict:
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
        A ResourceTagMappingList, which contains a list of resource ARNs and tags associated with each.

        NOTE: https://docs.aws.amazon.com/cli/latest/reference/resourcegroupstaggingapi/get-resources.html#output


    """
    try:
        return boto3.client("resourcegroupstaggingapi").get_resources(TagFilters=tag_filters)["ResourceTagMappingList"]
    except Exception as query_error:
        LOG.error("Failed to call get_resources from resource group tagging api: %s", query_error)
        return None


def _generate_statement_list(tag_filters: dict) -> List[dict]:
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

    resource_tag_mapping_list = _query_tagging_api(tag_filters)

    if resource_tag_mapping_list is None:
        LOG.error("Failed to receive get_resources response, cannot generate any IAM statements.")
        return []

    iam_statements = [_create_iam_statment(resource["ResourceARN"]) for resource in resource_tag_mapping_list]
    return iam_statements


def _comment_out_default_actions(raw_yaml_string: str) -> str:
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


def generate_test_runner_template_string(
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

    test_runner_template = _generate_base_test_runner_template_json(
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

    iam_statements = _generate_statement_list(tag_filters)

    # Attach the generated IAM statements to the Container IAM Role
    test_runner_template["Resources"]["ContainerIAMRole"]["Properties"]["Policies"][0]["PolicyDocument"][
        "Statement"
    ].extend(iam_statements)

    raw_yaml_template_string = to_yaml(json.dumps(test_runner_template))

    processed_yaml_template_string = _comment_out_default_actions(raw_yaml_template_string)

    return processed_yaml_template_string
