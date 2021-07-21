import os

import click

from samcli.lib.config.samconfig import SamConfig, DEFAULT_CONFIG_FILE_NAME

from samcli.commands.check.resources.Graph import Graph
from samcli.commands.check.resources.LambdaFunction import LambdaFunction
from samcli.commands.check.resources.LambdaFunctionPricing import LambdaFunctionPricing
from samcli.commands.check.resources.ApiGateway import ApiGateway
from samcli.commands.check.resources.DynamoDB import DynamoDB

from samcli.commands.check.lib.save_data import get_config_ctx


class LoadData:
    def __init__(self):
        self.graph = Graph()
        self.graph_toml = {}

    def get_data_from_toml(self, config_file):
        samconfig = get_config_ctx(config_file)

        return samconfig.get_all(["load"], "graph", "check")["all_graph_data"]

    def parse_toml_lambda_function_info(self):
        toml_lambda_function_info = self.graph_toml["lambda_function_pricing_info"]

        lambda_function_pricing = LambdaFunctionPricing()
        lambda_function_pricing.set_number_of_requests(int(toml_lambda_function_info["number_of_requests"]))
        lambda_function_pricing.set_average_duration(int(toml_lambda_function_info["average_duration"]))
        lambda_function_pricing.set_allocated_memory(float(toml_lambda_function_info["allocated_memory"]))
        lambda_function_pricing.set_allocated_memory_unit(str(toml_lambda_function_info["allocated_memory_unit"]))

        self.graph.set_lambda_function_pricing_info(lambda_function_pricing)

    def parse_resources(self):
        resources_toml = self.graph_toml["resources_to_analyze"]

        for resource_toml in resources_toml.values():
            self.parse_single_resource_toml(resource_toml)

    def parse_single_resource_toml(self, resource_toml, is_entry_point=True):
        resource_type = str(resource_toml["resource_type"])
        resource_name = str(resource_toml["resource_name"])
        resource_object = str(resource_toml["resource_object"])
        resource_children = resource_toml["children"]
        resource_tps = int(resource_toml["tps"])

        current_resource = None

        if resource_type == "AWS::Lambda::Function":
            resource_duration = int(resource_toml["duration"])
            current_resource = self.generate_lambda_function(
                resource_type,
                resource_name,
                resource_object,
                resource_tps,
                resource_duration,
            )

            self.graph.add_resource_to_analyze(current_resource)

        elif resource_type == "AWS::ApiGateway::RestApi":
            current_resource = self.generate_api_gateway(
                resource_type,
                resource_name,
                resource_object,
                resource_tps,
            )
        elif resource_type == "AWS::DynamoDB::Table":
            current_resource = self.generate_dynamoDB_table(
                resource_type,
                resource_name,
                resource_object,
                resource_tps,
            )

        for child_toml in resource_children:
            child_resource = self.parse_single_resource_toml(child_toml, False)
            current_resource.add_child(child_resource)

        if is_entry_point:
            self.graph.add_entry_point(current_resource)
        else:
            return current_resource

    def generate_lambda_function(
        self,
        resource_type,
        resource_name,
        resource_object,
        resource_tps,
        resource_duration,
    ):
        lambda_function = LambdaFunction(resource_object, resource_type, resource_name)
        lambda_function.set_duration(resource_duration)
        lambda_function.set_tps(resource_tps)

        return lambda_function

    def generate_api_gateway(
        self,
        resource_type,
        resource_name,
        resource_object,
        resource_tps,
    ):
        api_gateway = ApiGateway(resource_object, resource_type, resource_name)
        api_gateway.set_tps(resource_tps)

        return api_gateway

    def generate_dynamoDB_table(
        self,
        resource_type,
        resource_name,
        resource_object,
        resource_tps,
    ):
        dynamoBD_table = DynamoDB(resource_object, resource_type, resource_name)
        dynamoBD_table.set_tps(resource_tps)

        return dynamoBD_table

    def generate_graph_from_toml(self, config_file):
        self.graph_toml = self.get_data_from_toml(config_file)

        self.parse_toml_lambda_function_info()
        self.parse_resources()

        return self.graph
