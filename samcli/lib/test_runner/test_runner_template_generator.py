import copy
import json
import boto3
import re
from jinja2 import Template
from cfn_flip import to_yaml
from typing import *


def __getStatementTemplateCopy() -> dict:
    """
    Returns an object representing an empty IAM Policy Statement, with `Allow` action.

    NOTE: https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_policies_elements_statement.html

    Returns
    -------
    dict
        Empty IAM Policy Statement with `Allow` Action.
    """
    statementTemplate = {
        "Effect": "Allow",
        "Action": [],
        "Resource": "",
    }
    return copy.deepcopy(statementTemplate)


def __extractApiIdFromArn(apiArn: str) -> str:
    """
    Extracts an api id from an HTTP or REST api arn.

    NOTE: https://docs.aws.amazon.com/apigateway/latest/developerguide/arn-format-reference.html

    REST API Arn: `arn:partition:apigateway:region::/restapis/api-id`

    HTTP API Arn: `arn:partition:apigateway:region::/apis/api-id`

    Parameters
    ----------
    apiArn : str
        The arn of the HTTP or REST api from which the api id is extracted.

    Returns
    -------
    str
        The api id from the api arn.
    """

    return apiArn[apiArn.rindex("/") + 1 :]


def __getPermissionsMap() -> dict:
    """
    Returns a dictionary mapping a Regular Expression representing the arn of a specific resource to the default permissions generated for that resource.

    Returns
    -------
    defaultPermissionsMap : dict
        A dictionary mapping a Regular Expression representing the arn of a resource to a list of IAM Action permissions generated for that resource.
    """

    partitionEx = "(aws|aws-cn|aws-us-gov)"
    regionEx = "\w+-\w+-\d"
    accountEx = "\d{12}"

    defaultPermissionsMap = {
        # AWS::Lambda::Function
        f"^arn:{partitionEx}:lambda:{regionEx}:{accountEx}:function:[\\w-]+(:\\d+)?$": ["lambda:InvokeFunction"],
        # AWS::ApiGateway::Api
        f"^arn:{partitionEx}:apigateway:{regionEx}::\/apis\/\\w+$": ["execute-api:Invoke"],
        # AWS::ApiGateway::RestApi
        f"^arn:{partitionEx}:apigateway:{regionEx}::\/restapis\/\\w+$": ["execute-api:Invoke"],
        # AWS::SQS::Queue
        f"^arn:{partitionEx}:sqs:{regionEx}:{accountEx}:[\\w-]+$": ["sqs:SendMessage"],
        # AWS::S3::Bucket
        f"^arn:{partitionEx}:s3:::[\\w-]+$": ["s3:PutObject", "s3:GetObject"],
        # AWS::Dynamodb::Table
        f"^arn:{partitionEx}:dynamodb:{regionEx}:{accountEx}:table\/[\\w-]+$": [
            "dynamodb:GetItem",
            "dynamodb:PutItem",
        ],
        # AWS::StepFunctions::StateMachine
        f"^arn:{partitionEx}:states:{regionEx}:{accountEx}:stateMachine:[\\w-]+$": [
            "stepfunction:StartExecution",
            "stepfunction:StopExecution",
        ],
    }
    return defaultPermissionsMap


def __getPermissions(resourceArn: str) -> List[str]:
    """
    Returns a list of IAM Action permissions to generate given a resource arn.

    An empty list is returned if there are no IAM Action permissions to generate for the given resource.

    Parameters
    ----------
    resourceArn : str
        The arn of the resource for which IAM Action permissions are returned.

    Returns
    -------
    List[str]
        The list of IAM Action permissions to generate for a given resource.
    """

    permissionsMap = __getPermissionsMap()

    for arnExp in permissionsMap.keys():
        if re.search(arnExp, resourceArn) is not None:
            return permissionsMap[arnExp]

    return []


def __generateBaseTestRunnerTemplateJSON(
    jinjaTemplateJsonString: str,
    bucketName: str,
    ecsTaskExecRoleArn: str,
    imageUri: str,
    vpcId: str,
    cpu: int,
    memory: int,
) -> dict:
    """
    Renders a base jinja template with a set of parameters needed to create the Test Runner Stack.

    Parameters
    ----------
    jinjaTemplateJsonString : str
        The base jinja template to which parameters are substituted.

    bucketName : str
        The name of the S3 bucket used by the Test Runner Stack.

    ecsTaskExecRoleArn : str
        The ARN of the AWS ECS Task Execution Role used by the Test Runner Stack.

        NOTE: https://docs.aws.amazon.com/AmazonECS/latest/developerguide/task_execution_IAM_role.html

    imageUri : str
        The URI of the Image to be used by the Test Runner Fargate task definition.

    vpcId : str
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
        "vpc_id": vpcId,
        "ecs_task_exec_role_arn": ecsTaskExecRoleArn,
        "image_uri": imageUri,
        "s3_bucket_name": bucketName,
    }

    renderedTemplateString = Template(jinjaTemplateJsonString).render(data)
    return json.loads(renderedTemplateString)


def __queryTaggingApi(tagFilters: dict) -> dict:
    """
    Queries the Tagging API to retrieve the ARNs of every resource with the given tags.

    NOTE: https://docs.aws.amazon.com/cli/latest/reference/resourcegroupstaggingapi/get-resources.html#get-resources

    Parameters
    ----------
    tagFilters : dict
        The tag filters to restrict output to only those resources with the given tags.

        NOTE: https://docs.aws.amazon.com/cli/latest/reference/resourcegroupstaggingapi/get-resources.html#options

    Returns
    -------
    dict
        A response object containing ResourceTagMappingList, which contains a list of resource ARNs and tags associated with each.

        NOTE: https://docs.aws.amazon.com/cli/latest/reference/resourcegroupstaggingapi/get-resources.html#output


    """
    return boto3.client("resourcegroupstaggingapi").get_resources(TagFilters=tagFilters)


def __generateStatementList(tagFilters: dict) -> List[dict]:
    """
    Generates a list of IAM statements with default action permissions for resources with the given tags.

    Parameters
    ----------
    tagFilters : dict
        The tag filters to restrict output to only those resources with the given tags.

        NOTE: https://docs.aws.amazon.com/cli/latest/reference/resourcegroupstaggingapi/get-resources.html#options

    Returns
    -------
    List[dict]
        The list of JSON objects representing IAM statements corresponding to the resources specified by the given tags.
    """

    taggingApiResponse = __queryTaggingApi(tagFilters)

    iamStatements = []

    for resource in taggingApiResponse["ResourceTagMappingList"]:
        newStatement = __getStatementTemplateCopy()
        arn = resource["ResourceARN"]

        # CloudFormation will not accept IAM Policies with empty Action lists.
        # Adding this placeholder will not grant any permissions, but will allow the Test Runner Stack to deploy
        newStatement["Action"].append("placeholder:DeleteThis")
        newStatement["Action"].extend(
            # Default permissions are commented out
            ["# " + action for action in __getPermissions(arn)]
        )

        # https://docs.aws.amazon.com/apigateway/latest/developerguide/api-gateway-control-access-using-iam-policies-to-invoke-api.html
        if "# execute-api:Invoke" in newStatement["Action"]:
            apiId = __extractApiIdFromArn(arn)
            newStatement[
                "Resource"
            ] = f"!Sub arn:${{AWS::Partition}}:execute-api:${{AWS::Region}}:${{AWS::AccountId}}:{apiId}/<STAGE>/GET/<RESOURCE_PATH>"
        else:
            newStatement["Resource"] = arn

        iamStatements.append(newStatement)
    return iamStatements


def __commentOutDefaultOptions(rawYamlString: str) -> str:
    """
    Formats the given YAML string to remove quotes and move `#` to the other side of the list item `-`.

    This is to allow default permissions to actually be commented out.
    This string replacement will produce deterministic results, since the `rawYamlString` is deterministic.
    There will be no other instances of `- # ` other than the ones created during the template generation process.

    e.g.

        `- '# lambda:InvokeFunction'` => `# - lambda:InvokeFunction`
    """
    # Move comment hashtag to be in front of list items so they're properly commented out
    return rawYamlString.replace("'", "").replace("- # ", "# - ")


def generateTestRunnerTemplateString(
    jinjaTemplateJsonString: str,
    bucketName: str,
    ecsTaskExecRoleArn: str,
    imageUri: str,
    vpcId: str,
    tagFilters: dict,
    cpu: int = 256,
    memory: int = 512,
) -> str:

    """
        Generates a Test Runner CloudFormation Template based on a base jinja template and given parameters.

    Parameters
    ----------
    jinjaTemplateJsonString : str
        The base jinja template to which parameters are substituted.

    bucketName : str
        The name of the S3 bucket used by the Test Runner Stack.

    ecsTaskExecRoleArn : str
        The ARN of the AWS ECS Task Execution Role used by the Test Runner Stack.

        NOTE: https://docs.aws.amazon.com/AmazonECS/latest/developerguide/task_execution_IAM_role.html

    imageUri : str
        The URI of the Image to be used by the Test Runner Fargate task definition.

    vpcId : str
        The ID of the VPC associated with the Test Runner security group.

        NOTE: The security group (and associated VPC) is required to invoke the runTask API and run tests.

    cpu : int
        The CPU used by the Test Runner Task Definition. (DEFAULT = 256)

        NOTE: https://docs.aws.amazon.com/AmazonECS/latest/developerguide/task_definition_parameters.html#task_size

    memory : int
        The memory used by the Test Runner Task Definition. (DEFAULT = 512)

        NOTE: https://docs.aws.amazon.com/AmazonECS/latest/developerguide/task_definition_parameters.html#task_sizes

    tagFilters : dict
        The tag filters to restrict generating default IAM action permissions to those resources with the given tags.

        NOTE: https://docs.aws.amazon.com/cli/latest/reference/resourcegroupstaggingapi/get-resources.html#options

    Returns
    -------
    str
        A YAML string representing a complete Test Runner CloudFormation Template

    """

    testRunnerTemplate = __generateBaseTestRunnerTemplateJSON(
        jinjaTemplateJsonString,
        bucketName,
        ecsTaskExecRoleArn,
        imageUri,
        vpcId,
        cpu,
        memory,
    )

    iamStatements = __generateStatementList(tagFilters)

    # Attach the generated IAM statements to the Container IAM Role
    testRunnerTemplate["Resources"]["ContainerIAMRole"]["Properties"]["Policies"][0]["PolicyDocument"][
        "Statement"
    ].extend(iamStatements)

    rawYamlTemplateString = to_yaml(json.dumps(testRunnerTemplate))

    processedYamlString = __commentOutDefaultOptions(rawYamlTemplateString)

    return processedYamlString
