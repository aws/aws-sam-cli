"""
Graph data gets converted here to a format that can be saved into the samconfig.toml file
"""

import os
from typing import Any, Dict, List, Union

import click

from samcli.lib.config.samconfig import SamConfig, DEFAULT_CONFIG_FILE_NAME
from samcli.commands.check.resources.lambda_function import LambdaFunction
from samcli.commands.check.resources.api_gateway import ApiGateway
from samcli.commands.check.resources.dynamo_db import DynamoDB
from samcli.commands.check.resources.graph import CheckGraph

from samcli.commands._utils.resources import AWS_LAMBDA_FUNCTION, AWS_APIGATEWAY_RESTAPI, AWS_DYNAMODB_TABLE


class SaveGraphData:
    _graph: CheckGraph

    def __init__(self, graph: CheckGraph):
        self._graph = graph

    def _generate_lambda_toml(
        self,
        lambda_function: LambdaFunction,
        children_toml: Dict,
        entry_point_resource: Union[LambdaFunction, ApiGateway, DynamoDB, None],
    ):
        """Creates a dictionary of a lambda function object for the toml file

        Parameters
        ----------
            lambda_function: LambdaFunction
                The lambda function object from the graph
            children_toml: Dict
                all children resources of the current lambda function object generated in a dict format
            entry_point_resource: Union[LambdaFunction, ApiGateway, DynamoDB, None]
                The entry point resource for the current resource. Can be None if it is the entry point
                resource itself

        Returns:
            lambda_toml: Dict
                Returns the generated lambda function toml (dictionary) for the samconfig file
        """

        lambda_function_name = lambda_function.resource_name

        key = lambda_function_name + ":" + str(entry_point_resource)
        copied_lambda_function = self._graph.resources_to_analyze[key]

        lambda_toml = {
            "resource_object": "",
            "resource_type": copied_lambda_function.resource_type,
            "resource_name": copied_lambda_function.resource_name,
            "duration": copied_lambda_function.duration,
            "tps": copied_lambda_function.tps,
            "children": children_toml,
            "key": key,
            "path_to_resource": copied_lambda_function.path_to_resource,
        }

        return lambda_toml

    def _generate_resource_toml(
        self,
        resource: Union[LambdaFunction, ApiGateway, DynamoDB],
        entry_point_resource: Union[LambdaFunction, ApiGateway, DynamoDB, None],
    ):
        """
        Generates a dict for a single resource. This is recursively called for all
        children of a given resource

        Parameters
        ----------
            resource: Union[LambdaFunction, ApiGateway, DynamoDB]
                The resource from the graph to generate into a dict for the samconfig.toml file
            entry_point_resource: Union[LambdaFunction, ApiGateway, DynamoDB, None]
                The entry point resource for the current resource. Can be None if it is the entry point
                resource itself

        Returns
        -------
            resource_toml: dict
                A dict of the resource passed into this method

        """
        resource_type = resource.resource_type
        resource_name = resource.resource_name
        resource_toml = {}
        resource_children_toml: List = []

        if resource_type == AWS_LAMBDA_FUNCTION:
            resource_toml = self._generate_lambda_toml(resource, resource_children_toml, entry_point_resource)

        elif resource_type == AWS_APIGATEWAY_RESTAPI:
            resource_toml = {
                "resource_object": "",
                "resource_type": resource_type,
                "resource_name": resource_name,
                "tps": resource.tps,
                "children": resource_children_toml,
                "path_to_resource": resource.path_to_resource,
            }
        elif resource_type == AWS_DYNAMODB_TABLE:
            resource_toml = {
                "resource_object": "",
                "resource_type": resource_type,
                "resource_name": resource_name,
                "tps": resource.tps,
                "children": resource_children_toml,
                "path_to_resource": resource.path_to_resource,
            }

        resource_children = resource.children
        for child in resource_children:
            child_toml = self._generate_resource_toml(child, entry_point_resource)
            resource_children_toml.append(child_toml)

        return resource_toml

    def _parse_resources(
        self, resources: List[Union[LambdaFunction, ApiGateway, DynamoDB]], resources_to_analyze_toml: Dict
    ):
        """
        Parses each resource in the entry_point array from graph. All resources are either in this array,
        or they are a child of something in this array

        Parameters
        ----------
            resources: List[Union[LambdaFunction, ApiGateway, DynamoDB]]
                A list of all resources to save into the samconfig.toml file
            resources_to_analyze_toml: dict
                A dict of all resources that need to be analyzed once loaded from the samconfig.toml file
        """
        for resource in resources:
            entry_point_resource = resource.entry_point_resource
            resource_toml = self._generate_resource_toml(resource, entry_point_resource)
            key = resource.resource_name + ":" + str(entry_point_resource)
            resources_to_analyze_toml[key] = resource_toml

    def _get_lambda_function_pricing_info(self):
        """
        Gets the pricing information from the graph. Converts it into a dict

        Retruns
        -------
            dict
                A dict containing all info on lambda function pricing
        """
        lambda_pricing_info = self._graph.unique_pricing_info["LambdaFunction"]

        return {
            "number_of_requests": lambda_pricing_info.number_of_requests,
            "average_duration": lambda_pricing_info.average_duration,
            "allocated_memory": lambda_pricing_info.allocated_memory,
            "allocated_memory_unit": lambda_pricing_info.allocated_memory_unit,
        }

    def save_to_config_file(self, config_file: Any):
        """
        Saves the graph data into the samconfig.toml file

        Parameters
        ----------
            config_file: Any
                The samconfig.toml file that the data will be saved to
        """
        samconfig = get_config_ctx(config_file)

        resources_to_analyze_toml: dict = {}
        lambda_function_pricing_info_toml = {}

        resources = self._graph.entry_points

        self._parse_resources(resources, resources_to_analyze_toml)

        lambda_function_pricing_info_toml = self._get_lambda_function_pricing_info()

        graph_dict = {
            "resources_to_analyze": resources_to_analyze_toml,
            "lambda_function_pricing_info": lambda_function_pricing_info_toml,
        }

        samconfig.put(["load"], "graph", "all_graph_data", graph_dict, "check")
        samconfig.flush()


def get_config_ctx(config_file=None):
    """
    Gets the samconfig file so it can be modified
    """
    path = os.path.realpath("")
    ctx = click.get_current_context()

    samconfig_dir = getattr(ctx, "samconfig_dir", None)
    samconfig = SamConfig(
        config_dir=samconfig_dir if samconfig_dir else SamConfig.config_dir(template_file_path=path),
        filename=config_file or DEFAULT_CONFIG_FILE_NAME,
    )
    return samconfig
