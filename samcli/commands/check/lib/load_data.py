import logging

import tomlkit.exceptions

from samcli.commands.check.resources.Graph import Graph
from samcli.commands.check.resources.LambdaFunction import LambdaFunction
from samcli.commands.check.resources.LambdaFunctionPricing import LambdaFunctionPricing
from samcli.commands.check.resources.ApiGateway import ApiGateway
from samcli.commands.check.resources.DynamoDB import DynamoDB

from samcli.commands.check.lib.save_data import get_config_ctx

LOG = logging.getLogger(__name__)


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

        self.check_pricing_info(lambda_function_pricing)

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

        self.check_range(resource_tps, 0, float("inf"))

        current_resource = None

        if resource_type == "AWS::Lambda::Function":
            resource_duration = int(resource_toml["duration"])
            self.check_range(resource_duration, 0, 900000)
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
        else:
            raise ValueError("invalid type")

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

    def check_range(self, check_value, min_value, max_value):
        if check_value < min_value or check_value > max_value:
            raise ValueError("invalid number")

    def check_pricing_info(self, lambda_function_pricing):
        number_of_requests = lambda_function_pricing.get_number_of_requests()
        average_duration = lambda_function_pricing.get_average_duration()
        allocated_memory = lambda_function_pricing.get_allocated_memory()
        allocated_memory_unit = lambda_function_pricing.get_allocated_memory_unit()

        valid_units = ["MB", "GB"]
        # memory is in MB
        min_memory = 128
        max_memory = 10000
        min_requests = 0
        min_duration = 0
        max_duration = 900000

        if allocated_memory_unit not in valid_units:
            raise ValueError("invalid unit")

        if allocated_memory_unit == "GB":
            allocated_memory *= 1000

        self.check_range(number_of_requests, min_requests, float("inf"))
        self.check_range(average_duration, min_duration, max_duration)
        self.check_range(allocated_memory, min_memory, max_memory)

    def generate_graph_from_toml(self, config_file):
        try:
            self.graph_toml = self.get_data_from_toml(config_file)

            self.parse_toml_lambda_function_info()
            self.parse_resources()
        except TypeError as exception:
            LOG.error(
                "ERROR: A value in samconfig.toml was changed to an unexpected value type. Please undo all changes in the samconfig.toml file, or go through the sam check guided process again to re-write the data in samconfig.toml."
            )
            raise exception
        except tomlkit.exceptions.NonExistentKey as exception:
            LOG.error(
                "ERROR: a key value was changed in samconfig.toml. Please undo all changes in the samconfig.toml file, or go through the sam check guided process again to re-write the data in samconfig.toml."
            )
            raise exception

        except ValueError as exception:
            exception_type = exception.args[0]
            if exception_type == "invalid type":
                LOG.error(
                    "ERROR: An incorrect resource type was detected. Please undo all changes in the samconfig.toml file, or go through the sam check guided process again to re-write the data in samconfig.toml."
                )
            elif exception_type == "invalid number":
                LOG.error(
                    "ERROR: A value was outside of the accepted range. Please undo all changes in the samconfig.toml file, or go through the sam check guided process again to re-write the data in samconfig.toml."
                )
            elif exception_type == "invalid unit":
                LOG.error(
                    "ERROR: An invalid memory unit was detected. Please undo all changes in the samconfig.toml file, or go through the sam check guided process again to re-write the data in samconfig.toml."
                )

            raise exception

        return self.graph
