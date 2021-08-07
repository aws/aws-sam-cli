import os

import click

from samcli.lib.config.samconfig import SamConfig, DEFAULT_CONFIG_FILE_NAME


class SaveGraphData:
    def __init__(self, graph):
        self.graph = graph

    def generate_lambda_toml(self, lambda_function, children_toml, entry_point_resource):
        """Creates a dictionary of a lambda function object for the toml file
        Args:
            lambda_function ([LambdaFunction]): The lambda function object

        Returns:
            [dict]: Returns the generated lambda function toml (dictionary) for the samconfig file
        """

        lambda_function_name = lambda_function.resource_name

        key = lambda_function_name + ":" + entry_point_resource
        copied_lambda_function = self.graph.resources_to_analyze[key]

        lambda_toml = {
            "resource_object": "",
            "resource_type": copied_lambda_function.resource_type,
            "resource_name": copied_lambda_function.resource_name,
            "duration": copied_lambda_function.duration,
            "tps": copied_lambda_function.tps,
            "children": children_toml,
            "key": key,
        }

        return lambda_toml

    def generate_resource_toml(self, resource, entry_point_resource):
        """
        Generates a dict for a single resource. This is recursively called for all
        children of a given resource
        """
        resource_type = resource.resource_type
        resource_name = resource.resource_name
        resource_toml = {}
        resource_children_toml = []

        if resource_type == "AWS::Lambda::Function":
            resource_toml = self.generate_lambda_toml(resource, resource_children_toml, entry_point_resource)

        elif resource_type == "AWS::ApiGateway::RestApi":
            resource_toml = {
                "resource_object": "",
                "resource_type": resource_type,
                "resource_name": resource_name,
                "tps": resource.tps,
                "children": resource_children_toml,
            }
        elif resource_type == "AWS::DynamoDB::Table":
            resource_toml = {
                "resource_object": "",
                "resource_type": resource_type,
                "resource_name": resource_name,
                "tps": resource.tps,
                "children": resource_children_toml,
            }

        resource_children = resource.children
        for child in resource_children:
            child_toml = self.generate_resource_toml(child, entry_point_resource)
            resource_children_toml.append(child_toml)

        return resource_toml

    def parse_resources(self, resources, resources_to_analyze_toml):
        """
        Parses each resource in the entry_point array from graph. All resources are either in this array,
        or they are a child of something in this array
        """
        for resource in resources:
            entry_point_resource = resource.entry_point_resource
            resource_toml = self.generate_resource_toml(resource, entry_point_resource)
            key = resource.resource_name + ":" + entry_point_resource
            resources_to_analyze_toml[key] = resource_toml

    def get_lambda_function_pricing_info(self):
        """
        Gets the pricing information from the graph. Converts it into a dict
        """
        lambda_pricing_info = self.graph.unique_pricing_info["LambdaFunction"]

        return {
            "number_of_requests": lambda_pricing_info.number_of_requests,
            "average_duration": lambda_pricing_info.average_duration,
            "allocated_memory": lambda_pricing_info.allocated_memory,
            "allocated_memory_unit": lambda_pricing_info.allocated_memory_unit,
        }

    def save_to_config_file(self, config_file):
        """
        Saves the graph data into the samconfig.toml file
        """
        samconfig = get_config_ctx(config_file)

        resources_to_analyze_toml = {}
        lambda_function_pricing_info_toml = {}

        resources = self.graph.entry_points

        self.parse_resources(resources, resources_to_analyze_toml)

        lambda_function_pricing_info_toml = self.get_lambda_function_pricing_info()

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
