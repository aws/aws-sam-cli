"""
The producer for the 'sam list endpoints' command
"""

import dataclasses
import json
import logging
from enum import Enum
from typing import Any, Dict, List

from botocore.exceptions import BotoCoreError, ClientError

from samcli.commands._utils.template import get_template_data
from samcli.commands.list.exceptions import (
    SamListLocalResourcesNotFoundError,
    SamListUnknownBotoCoreError,
    SamListUnknownClientError,
)
from samcli.lib.list.endpoints.endpoints_def import EndpointsDef
from samcli.lib.list.list_interfaces import Producer
from samcli.lib.list.resources.resource_mapping_producer import ResourceMappingProducer
from samcli.lib.providers.provider import Stack
from samcli.lib.providers.sam_stack_provider import SamLocalStackProvider
from samcli.lib.utils.boto_utils import get_client_error_code
from samcli.lib.utils.resources import (
    AWS_APIGATEWAY_BASE_PATH_MAPPING,
    AWS_APIGATEWAY_DOMAIN_NAME,
    AWS_APIGATEWAY_RESTAPI,
    AWS_APIGATEWAY_V2_API,
    AWS_APIGATEWAY_V2_BASE_PATH_MAPPING,
    AWS_APIGATEWAY_V2_DOMAIN_NAME,
    AWS_LAMBDA_FUNCTION,
    AWS_LAMBDA_FUNCTION_URL,
)

ENDPOINT_RESOURCE_TYPES = {AWS_LAMBDA_FUNCTION, AWS_APIGATEWAY_RESTAPI, AWS_APIGATEWAY_V2_API}
RESOURCE_DESCRIPTION = "ResourceDescription"
PROPERTIES = "Properties"
FUNCTION_URL = "FunctionUrl"
STACK_RESOURCES = "StackResources"
RESOURCE_TYPE = "ResourceType"
PHYSICAL_RESOURCE_ID = "PhysicalResourceId"
LOGICAL_RESOURCE_ID = "LogicalResourceId"
REST_API_ID = "RestApiId"
API_ID = "ApiId"
DOMAIN_NAME = "DomainName"
BODY = "Body"
PATHS = "paths"

LOG = logging.getLogger(__name__)


class APIGatewayEnum(Enum):
    API_GATEWAY = 1
    API_GATEWAY_V2 = 2


class EndpointsProducer(ResourceMappingProducer, Producer):
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
        parameter_overrides=None,
    ):
        """
        Parameters
        ----------
        stack_name: str
            The name of the stack
        region: Optional[str]
            The region of the stack
        profile: Optional[str]
            Optional profile to be used
        template_file: Optional[str]
            The location of the template file. If one is not specified, the default will be "template.yaml" in the CWD
        cloudformation_client: CloudFormation
            The CloudFormation client
        iam_client: IAM
            The IAM client
        cloudcontrol_client: CloudControl
            The CloudControl client
        apigateway_client: APIGateway
            The APIGateway client
        apigatewayv2_client: APIGatewayV2
            The APIGatewayV2 client
        mapper: Mapper
            The mapper used to map data to the format needed for the consumer provided
        consumer: ListInfoPullerConsumer
            The consumer used to output the data
        parameter_overrides: Optional[dict]
            Dictionary of parameters to override in the template
        """
        super().__init__(
            stack_name,
            region,
            profile,
            template_file,
            cloudformation_client,
            iam_client,
            mapper,
            consumer,
            parameter_overrides,
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
            response = self.cloudcontrol_client.get_resource(TypeName=AWS_LAMBDA_FUNCTION_URL, Identifier=identifier)
            if not response.get(RESOURCE_DESCRIPTION, {}).get(PROPERTIES, {}):
                return "-"
            response_dict = json.loads(response.get(RESOURCE_DESCRIPTION, {}).get(PROPERTIES, {}))
            furl = response_dict.get(FUNCTION_URL, "-")
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
            elif api_type == APIGatewayEnum.API_GATEWAY_V2:
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
        """
        Builds the default api gateway endpoints

        Parameters
        ----------
        physical_id: str
            The physical ID of the api resource
        stages: list
            A list of stages for the api resource

        Returns
        -------
        api_list: List[Any]
            The list of default api gateway endpoints
        """
        api_list = []
        for stage in stages:
            api_list.append(f"https://{physical_id}.execute-api.{self.region}.amazonaws.com/{stage}")
        return api_list

    def get_api_gateway_endpoint(
        self, deployed_resource: Dict[Any, Any], custom_domain_substitute_dict: Dict[Any, Any]
    ) -> Any:
        """
        Gets the API gateway endpoints for APIGateway and APIGatewayV2 APIs

        Parameters
        ----------
        deployed_resource: Dict[Any, Any]
            Dictionary containing the resource info of the deployed API
        custom_domain_substitute_dict: Dict[Any, Any]
            Dictionary containing the mappings of the custom domains for APIs

        Returns
        -------
        endpoint: Any
            The endpoint(s) of the current API resource
        """
        endpoint: Any
        stages = self.get_stage_list(
            deployed_resource.get(PHYSICAL_RESOURCE_ID, ""),
            get_api_type_enum(deployed_resource.get(RESOURCE_TYPE, "")),
        )
        if deployed_resource.get(LOGICAL_RESOURCE_ID, "") in custom_domain_substitute_dict:
            endpoint = custom_domain_substitute_dict.get(deployed_resource.get(LOGICAL_RESOURCE_ID, ""), "-")
        else:
            endpoint = self.build_api_gw_endpoints(deployed_resource.get(PHYSICAL_RESOURCE_ID, ""), stages)
        return endpoint

    def get_cloud_endpoints(self, stacks: list) -> list:
        """
        Gets a list of cloud endpoints resources

        Parameters
        ----------
        stacks: list
            A list containing the local stack

        Returns
        -------
        endpoints_list: List[Any]
            A list of cloud endpoints resources
        """
        endpoints_list = []
        local_stack = stacks[0]
        local_stack_resources = local_stack.resources
        seen_endpoints = set()
        response = self.get_resources_info()
        response_domain_dict = get_response_domain_dict(response)
        custom_domain_substitute_dict = get_custom_domain_substitute_list(response, stacks, response_domain_dict)

        # Iterate over the deployed resources, collect relevant endpoint data for functions and APIGW resources
        for deployed_resource in response.get(STACK_RESOURCES, {}):
            if deployed_resource.get(RESOURCE_TYPE, "") in ENDPOINT_RESOURCE_TYPES:
                endpoint_function_url: Any
                paths_and_methods: Any
                endpoint_function_url = "-"
                paths_and_methods = "-"

                # Collect function URLs
                if deployed_resource.get(RESOURCE_TYPE, "") == AWS_LAMBDA_FUNCTION:
                    endpoint_function_url = self.get_function_url(deployed_resource.get(PHYSICAL_RESOURCE_ID, ""))

                # Collect APIGW endpoints and methods
                elif deployed_resource.get(RESOURCE_TYPE, "") in (AWS_APIGATEWAY_RESTAPI, AWS_APIGATEWAY_V2_API):
                    endpoint_function_url = self.get_api_gateway_endpoint(
                        deployed_resource, custom_domain_substitute_dict
                    )
                    paths_and_methods = get_methods_and_paths(
                        deployed_resource.get(LOGICAL_RESOURCE_ID, ""), local_stack
                    )

                endpoint_data = EndpointsDef(
                    LogicalResourceId=deployed_resource.get(LOGICAL_RESOURCE_ID, "-"),
                    PhysicalResourceId=deployed_resource.get(PHYSICAL_RESOURCE_ID, "-"),
                    CloudEndpoint=endpoint_function_url,
                    Methods=paths_and_methods,
                )
                endpoints_list.append(dataclasses.asdict(endpoint_data))
                seen_endpoints.add(deployed_resource.get(LOGICAL_RESOURCE_ID, ""))

        # Loop over resources all stack resources and collect data for resources not yet deployed
        for local_resource in local_stack_resources:
            local_resource_type = local_stack_resources.get(local_resource, {}).get("Type", "")
            paths_and_methods = "-"
            # Check if a resources has already been added to the endpoints list, if not, add it
            if local_resource_type in ENDPOINT_RESOURCE_TYPES and local_resource not in seen_endpoints:
                # We don't support function URLs locally, so this can only be APIGW endpoint data
                if local_resource_type in (AWS_APIGATEWAY_RESTAPI, AWS_APIGATEWAY_V2_API):
                    paths_and_methods = get_methods_and_paths(local_resource, local_stack)
                endpoint_data = EndpointsDef(
                    LogicalResourceId=local_resource,
                    PhysicalResourceId="-",
                    CloudEndpoint="-",
                    Methods=paths_and_methods,
                )
                endpoints_list.append(dataclasses.asdict(endpoint_data))

        return endpoints_list

    def produce(self):
        """
        The producer function for the endpoints resources command
        """
        sam_template = get_template_data(self.template_file)

        translated_dict = self.get_translated_dict(template_file_dict=sam_template)
        stacks, _ = SamLocalStackProvider.get_stacks(template_file="", template_dictionary=translated_dict)
        validate_stack(stacks)

        endpoints_list: list

        if self.stack_name:
            endpoints_list = self.get_cloud_endpoints(stacks)
        else:
            endpoints_list = get_local_endpoints(stacks)
        mapped_output = self.mapper.map(endpoints_list)
        self.consumer.consume(mapped_output)


def validate_stack(stacks: list):
    """
    Checks if the stack non-empty and contains stack resources and raises exceptions accordingly

    Parameters
    ----------
    stacks: list
        A list containing the stack
    """

    if not stacks or not hasattr(stacks[0], "resources") or not stacks[0].resources:
        raise SamListLocalResourcesNotFoundError(msg="No local resources found.")


def get_local_endpoints(stacks: list) -> list:
    """
    Gets a list of local endpoints resources based on the local stack

    Parameters
    ----------
    stacks: list
        A list containing the stack

    Returns
    -------
    endpoints_list: list
        A list containing the endpoints resources and their information
    """
    endpoints_list = []
    paths_and_methods: Any
    local_stack = stacks[0]
    local_stack_resources = local_stack.resources
    for local_resource in local_stack_resources:
        local_resource_type = local_stack_resources.get(local_resource, {}).get("Type", "")
        if local_resource_type in ENDPOINT_RESOURCE_TYPES:
            paths_and_methods = "-"
            if local_resource_type in (AWS_APIGATEWAY_RESTAPI, AWS_APIGATEWAY_V2_API):
                paths_and_methods = get_methods_and_paths(local_resource, local_stack)
            # Set the PhysicalID to "-" if there is no corresponding PhysicalID
            endpoint_data = EndpointsDef(
                LogicalResourceId=local_resource,
                PhysicalResourceId="-",
                CloudEndpoint="-",
                Methods=paths_and_methods,
            )
            endpoints_list.append(dataclasses.asdict(endpoint_data))
    return endpoints_list


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
    if resource_type == AWS_APIGATEWAY_V2_API:
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
    local_stack = stacks[0]
    local_stack_resources = local_stack.resources
    for resource in response.get(STACK_RESOURCES, {}):
        # Collect custom domain data for APIGW V1 resources
        if resource.get(RESOURCE_TYPE, "") == AWS_APIGATEWAY_BASE_PATH_MAPPING:
            local_mapping = local_stack_resources.get(resource.get(LOGICAL_RESOURCE_ID, ""), {}).get(PROPERTIES, {})
            rest_api_id = local_mapping.get(REST_API_ID, "")
            domain_id = local_mapping.get(DOMAIN_NAME, "")
            if domain_id in response_domain_dict:
                if rest_api_id not in custom_domain_substitute_dict:
                    custom_domain_substitute_dict[rest_api_id] = [response_domain_dict.get(domain_id, None)]
                else:
                    custom_domain_substitute_dict[rest_api_id].append(response_domain_dict.get(domain_id, None))

        # Collect custom domain data for APIGW V2 resources
        elif resource.get(RESOURCE_TYPE, "") == AWS_APIGATEWAY_V2_BASE_PATH_MAPPING:
            local_mapping = local_stack_resources.get(resource.get(LOGICAL_RESOURCE_ID, ""), {}).get(PROPERTIES, {})
            rest_api_id = local_mapping.get(API_ID, "")
            domain_id = local_mapping.get(DOMAIN_NAME, "")
            if domain_id in response_domain_dict:
                if rest_api_id not in custom_domain_substitute_dict:
                    custom_domain_substitute_dict[rest_api_id] = [response_domain_dict.get(domain_id, None)]
                else:
                    custom_domain_substitute_dict[rest_api_id].append(response_domain_dict.get(domain_id, None))
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
    for resource in response.get(STACK_RESOURCES, {}):
        if (
            resource.get(RESOURCE_TYPE, "") == AWS_APIGATEWAY_DOMAIN_NAME
            or resource.get(RESOURCE_TYPE, "") == AWS_APIGATEWAY_V2_DOMAIN_NAME
        ):
            response_domain_dict[resource.get(LOGICAL_RESOURCE_ID, "")] = (
                f'https://{resource.get(PHYSICAL_RESOURCE_ID, "")}'
            )
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
    if not stack.resources.get(logical_id, {}).get(PROPERTIES, {}).get(BODY, {}).get(PATHS, {}):
        return method_paths_list
    paths_dict = stack.resources.get(logical_id, {}).get(PROPERTIES, {}).get(BODY, {}).get(PATHS, {})
    for path in paths_dict:
        method_list = []
        for method in paths_dict.get(path, ""):
            method_list.append(method)
        path_item = path + f"{method_list}"
        method_paths_list.append(path_item)
    return method_paths_list
