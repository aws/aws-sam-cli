"""
The producer for the 'sam list testable-resources' command
"""
import dataclasses
import logging
from typing import Dict, List, Any
from enum import Enum
import json
from botocore.exceptions import ClientError, BotoCoreError
from samcli.commands.list.exceptions import (
    SamListUnknownBotoCoreError,
    SamListLocalResourcesNotFoundError,
    SamListUnknownClientError,
)
from samcli.lib.list.list_interfaces import Producer
from samcli.lib.providers.sam_stack_provider import SamLocalStackProvider
from samcli.lib.providers.provider import Stack
from samcli.commands._utils.template import get_template_data
from samcli.lib.list.testable_resources.testable_res_def import TestableResDef
from samcli.lib.list.resources.resource_mapping_producer import ResourceMappingProducer
from samcli.lib.utils.boto_utils import get_client_error_code

LOG = logging.getLogger(__name__)


class APIGatewayEnum(Enum):
    API_GATEWAY = 1
    API_GATEWAY_V2 = 2


class TestableResourcesProducer(ResourceMappingProducer, Producer):
    def __init__(
        self,
        stack_name,
        region,
        profile,
        template_file,
        cloudformation_client,
        iam_client,
        cloudcontrol_client,
        apigateway_client,
        apigatewayv2_client,
        mapper,
        consumer,
    ):
        super().__init__(
            stack_name, region, profile, template_file, cloudformation_client, iam_client, mapper, consumer
        )
        self.stack_name = stack_name
        self.region = region
        self.profile = profile
        self.template_file = template_file
        self.cloudformation_client = cloudformation_client
        self.iam_client = iam_client
        self.cloudcontrol_client = cloudcontrol_client
        self.apigateway_client = apigateway_client
        self.apigatewayv2_client = apigatewayv2_client
        self.mapper = mapper
        self.consumer = consumer

    def get_function_url(self, identifier: str) -> Any:
        """
        Gets the function url of a Lambda Function

        Parameters
        ----------
        identifier: str
            The identifier or physical ID

        Returns
        -------
        furl: str
            The function url in the form of a string
        """
        try:
            response = self.cloudcontrol_client.get_resource(TypeName="AWS::Lambda::Url", Identifier=identifier)
            if not response.get("ResourceDescription", {}).get("Properties", {}):
                return "-"
            response_dict = json.loads(response.get("ResourceDescription", {}).get("Properties", {}))
            furl = response_dict.get("FunctionUrl", "-")
            return furl
        except ClientError as e:
            if get_client_error_code(e) == "ResourceNotFoundException":
                return "-"
            LOG.error("ClientError Exception : %s", str(e))
            raise SamListUnknownClientError(msg=str(e)) from e

    def get_stage_list(self, api_id: str, api_type: APIGatewayEnum) -> List[Any]:
        """
        Gets a list of stages for a given api of type AWS::ApiGateway::RestApi or AWS::ApiGatewayV2::Api

        Parameters
        ----------
        api_id: str
            The api id or rest api id of the api
        api_type: APIGatewayEnum
            The type of api, AWS::ApiGateway::RestApi or AWS::ApiGatewayV2::Api

        Returns
        -------
        response_list: List[Any]
            A list of stages for the api
        """
        response_list: List[Any]
        try:
            response_list = []
            response: dict
            search_key: str
            stage_name_key: str
            if api_type == APIGatewayEnum.API_GATEWAY:
                response = self.apigateway_client.get_stages(restApiId=api_id)
                search_key = "item"
                stage_name_key = "stageName"
            else:
                response = self.apigatewayv2_client.get_stages(ApiId=api_id)
                search_key = "Items"
                stage_name_key = "StageName"
            if not response.get(search_key, []):
                return response_list
            for item in response.get(search_key, []):
                if item.get(stage_name_key, None):
                    response_list.append(item.get(stage_name_key, ""))
            return response_list
        except ClientError as e:
            if get_client_error_code(e) == "NotFoundException":
                return []
            LOG.error("ClientError Exception : %s", str(e))
            raise SamListUnknownClientError(msg=str(e)) from e
        except BotoCoreError as e:
            LOG.error("Botocore Exception : %s", str(e))
            raise SamListUnknownBotoCoreError(msg=str(e)) from e

    def build_api_gw_endpoints(self, physical_id: str, stages: list) -> list:
        api_list = []
        for stage in stages:

            api_list.append(f"https://{physical_id}.execute-api.{self.region}.amazonaws.com/{stage}")
        return api_list

    def produce(self):
        """
        The producer function for the testable resources command
        """
        sam_template = get_template_data(self.template_file)

        translated_dict = self.get_translated_dict(template_file_dict=sam_template)
        stacks, _ = SamLocalStackProvider.get_stacks(template_file="", template_dictionary=translated_dict)
        validate_stack(stacks)
        seen_testable_resources = set()
        testable_resources_list = []
        testable_resource_types = {"AWS::Lambda::Function", "AWS::ApiGateway::RestApi", "AWS::ApiGatewayV2::Api"}
        if self.stack_name:
            response = self.get_resources_info()
            response_domain_dict = get_response_domain_dict(response)
            custom_domain_substitute_dict = get_custom_domain_substitute_list(response, stacks, response_domain_dict)

            for deployed_resource in response["StackResources"]:
                if deployed_resource["ResourceType"] in testable_resource_types:
                    endpoint_function_url = "-"
                    paths_and_methods = "-"
                    if deployed_resource["ResourceType"] == "AWS::Lambda::Function":
                        endpoint_function_url = self.get_function_url(deployed_resource["PhysicalResourceId"])

                    elif deployed_resource["ResourceType"] in ("AWS::ApiGateway::RestApi", "AWS::ApiGatewayV2::Api"):
                        stages = self.get_stage_list(
                            deployed_resource["PhysicalResourceId"],
                            get_api_type_enum(deployed_resource["ResourceType"]),
                        )
                        if deployed_resource["LogicalResourceId"] in custom_domain_substitute_dict:
                            endpoint_function_url = custom_domain_substitute_dict[
                                deployed_resource["LogicalResourceId"]
                            ]
                        else:
                            endpoint_function_url = self.build_api_gw_endpoints(
                                deployed_resource["PhysicalResourceId"], stages
                            )
                        paths_and_methods = get_methods_and_paths(deployed_resource["LogicalResourceId"], stacks[0])

                    testable_resource_data = TestableResDef(
                        LogicalResourceId=deployed_resource["LogicalResourceId"],
                        PhysicalResourceId=deployed_resource["PhysicalResourceId"],
                        CloudEndpointOrFURL=endpoint_function_url,
                        Methods=paths_and_methods,
                    )
                    testable_resources_list.append(dataclasses.asdict(testable_resource_data))
                    seen_testable_resources.add(deployed_resource["LogicalResourceId"])
            for local_resource in stacks[0].resources:
                local_resource_type = stacks[0].resources[local_resource]["Type"]
                paths_and_methods = "-"
                if local_resource_type in testable_resource_types and local_resource not in seen_testable_resources:
                    if local_resource_type in ("AWS::ApiGateway::RestApi", "AWS::ApiGatewayV2::Api"):
                        paths_and_methods = get_methods_and_paths(local_resource, stacks[0])
                    testable_resource_data = TestableResDef(
                        LogicalResourceId=local_resource,
                        PhysicalResourceId="-",
                        CloudEndpointOrFURL="-",
                        Methods=paths_and_methods,
                    )
                    testable_resources_list.append(dataclasses.asdict(testable_resource_data))
        else:
            testable_resources_list = get_local_testable_resources(stacks, testable_resource_types)
        mapped_output = self.mapper.map(testable_resources_list)
        self.consumer.consume(mapped_output)


def validate_stack(stacks: list):
    """
    Checks if the stack non-empty and contains stack resources and raises exceptions accordingly

    Parameters
    ----------
    stacks: list
        A list containing the stack
    """
    if not stacks or not stacks[0].resources:
        raise SamListLocalResourcesNotFoundError(msg="No local resources found.")


def get_local_testable_resources(stacks: list, testable_resource_types: set) -> list:
    """
    Gets a list of local testable resources based on the local stack

    Parameters
    ----------
    stacks: list
        A list containing the stack
    testable_resource_types: set
        A set of resources types that should be displayed by testable resources

    Returns
    -------
    testable_resources_list: list
        A list containing the testable resources and their information
    """
    testable_resources_list = []
    paths_and_methods: Any
    for local_resource in stacks[0].resources:
        local_resource_type = stacks[0].resources[local_resource]["Type"]
        if local_resource_type in testable_resource_types:
            paths_and_methods = "-"
            if local_resource_type in ("AWS::ApiGateway::RestApi", "AWS::ApiGatewayV2::Api"):
                paths_and_methods = get_methods_and_paths(local_resource, stacks[0])
            # Set the PhysicalID to "-" if there is no corresponding PhysicalID
            testable_resource_data = TestableResDef(
                LogicalResourceId=local_resource,
                PhysicalResourceId="-",
                CloudEndpointOrFURL="-",
                Methods=paths_and_methods,
            )
            testable_resources_list.append(dataclasses.asdict(testable_resource_data))
    return testable_resources_list


def get_api_type_enum(resource_type: str) -> APIGatewayEnum:
    """
    Gets the APIGatewayEnum associated with the input resource type

    Parameters
    ----------
    resource_type: str
        The type of the resource

    Returns
    -------
    The APIGatewayEnum associated with the input resource type
    """
    if resource_type == "AWS::ApiGatewayV2::Api":
        return APIGatewayEnum.API_GATEWAY_V2
    return APIGatewayEnum.API_GATEWAY


def get_custom_domain_substitute_list(
    response: Dict[Any, Any], stacks: list, response_domain_dict: Dict[str, str]
) -> Dict[Any, Any]:
    """
    Gets a dictionary containing the custom domain lists that map back to the original api

    Parameters
    ----------
    response: Dict[Any, Any]
        The response containing the cloud stack resources information
    stacks: list
        A list containing the local stack
    response_domain_dict: Dict
        A dictionary containing the custom domains
    Returns
    -------
    custom_domain_substitute_dict: Dict[Any, Any]
        A dict containing the custom domain lists mapped to the original apis
    """
    custom_domain_substitute_dict = {}
    for resource in response["StackResources"]:
        if resource["ResourceType"] == "AWS::ApiGateway::BasePathMapping":
            local_mapping = stacks[0].resources[resource["LogicalResourceId"]]["Properties"]
            rest_api_id = local_mapping["RestApiId"]
            domain_id = local_mapping["DomainName"]
            if domain_id in response_domain_dict:
                if rest_api_id not in custom_domain_substitute_dict:
                    custom_domain_substitute_dict[rest_api_id] = [response_domain_dict[domain_id]]
                else:
                    custom_domain_substitute_dict[rest_api_id].append(response_domain_dict[domain_id])
        elif resource["ResourceType"] == "AWS::ApiGatewayV2::ApiMapping":
            local_mapping = stacks[0].resources[resource["LogicalResourceId"]]["Properties"]
            rest_api_id = local_mapping["ApiId"]
            domain_id = local_mapping["DomainName"]
            if domain_id in response_domain_dict:
                if rest_api_id not in custom_domain_substitute_dict:
                    custom_domain_substitute_dict[rest_api_id] = [response_domain_dict[domain_id]]
                else:
                    custom_domain_substitute_dict[rest_api_id].append(response_domain_dict[domain_id])
    return custom_domain_substitute_dict


def get_response_domain_dict(response: Dict[Any, Any]) -> Dict[str, str]:
    """
    Gets a dictionary containing the custom domains

    Parameters
    ----------
    response: Dict[Any, Any]
        The response containing the cloud stack resources information

    Returns
    -------
    response_domain_dict: Dict[str, str]
        A dict containing the custom domains
    """
    response_domain_dict = {}
    for resource in response["StackResources"]:
        if (
            resource["ResourceType"] == "AWS::ApiGateway::DomainName"
            or resource["ResourceType"] == "AWS::ApiGatewayV2::DomainName"
        ):
            response_domain_dict[resource["LogicalResourceId"]] = "https://" + resource["PhysicalResourceId"]
    return response_domain_dict


def get_methods_and_paths(logical_id: str, stack: Stack) -> list:
    """
    Gets the methods and paths for apis based on the stack and the logical ID

    Parameters
    ----------
    logical_id: str
        The logical ID of the api
    stack: Stack
        The stack to retrieve the methods and paths from

    Returns
    -------
    method_paths_list: list
        A list containing the methods and paths of the api
    """
    method_paths_list: List[Any]
    method_paths_list = []
    if not stack.resources:
        raise SamListLocalResourcesNotFoundError(msg="No local resources found.")
    if not stack.resources.get(logical_id, {}).get("Properties", {}).get("Body", {}).get("paths", {}):
        return method_paths_list
    paths_dict = stack.resources.get(logical_id, {}).get("Properties", {}).get("Body", {}).get("paths", {})
    for path in paths_dict:
        method_list = []
        for method in paths_dict[path]:
            method_list.append(method)
        path_item = path + f"{method_list}"
        method_paths_list.append(path_item)
    return method_paths_list
