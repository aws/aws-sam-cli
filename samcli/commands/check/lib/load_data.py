"""
Data gets loaded from the samconfig.toml file here and converted into a format
that can be entered into the graph
"""

import logging
from typing import Any, Dict, List

import tomlkit.exceptions

from samcli.commands.check.resources.graph import CheckGraph
from samcli.commands.check.resources.lambda_function import LambdaFunction
from samcli.commands.check.resources.lambda_function_pricing import LambdaFunctionPricing
from samcli.commands.check.resources.api_gateway import ApiGateway
from samcli.commands.check.resources.dynamo_db import DynamoDB

from samcli.commands._utils.resources import AWS_LAMBDA_FUNCTION, AWS_APIGATEWAY_RESTAPI, AWS_DYNAMODB_TABLE

from samcli.commands.check.lib.save_data import get_config_ctx

LOG = logging.getLogger(__name__)


class LoadData:
    _graph: CheckGraph
    _graph_toml: Dict

    def __init__(self):
        self._graph = CheckGraph([])
        self._graph_toml = {}

    def _parse_toml_lambda_function_info(self):
        """
        Parses the toml file data for the resources and pricing info
        """
        toml_lambda_function_info = self._graph_toml["lambda_function_pricing_info"]

        lambda_function_pricing = LambdaFunctionPricing()
        lambda_function_pricing.number_of_requests = int(toml_lambda_function_info["number_of_requests"])
        lambda_function_pricing.average_duration = int(toml_lambda_function_info["average_duration"])
        lambda_function_pricing.allocated_memory = float(toml_lambda_function_info["allocated_memory"])
        lambda_function_pricing.allocated_memory_unit = str(toml_lambda_function_info["allocated_memory_unit"])

        _check_pricing_info(lambda_function_pricing)

        self._graph.unique_pricing_info["LambdaFunction"] = lambda_function_pricing

    def _parse_resources(self):
        """
        Parses each resource from the toml file
        """
        resources_toml = self._graph_toml["resources_to_analyze"]

        for resource_toml in resources_toml.values():
            self._parse_single_resource_toml(resource_toml)

    def _parse_single_resource_toml(self, resource_toml: Dict, is_entry_point: bool = True):
        """
        Parses a single resource dict from the toml file

        Parameters
        ----------
            resource_toml: Dict
                The dict of a single resource from the toml file
            is_entry_point: bool, optional
                A bool representing if the given resource is an entry point or not. Defaults to True.

        Raises:
            ValueError
                Raises an error if a resource type is not of an expected value

        Returns:
            current_resource
                The current reousrce object that will be apart of the graph
        """
        resource_type = str(resource_toml["resource_type"])
        resource_name = str(resource_toml["resource_name"])
        resource_object = str(resource_toml["resource_object"])
        resource_children = resource_toml["children"]
        resource_tps = int(resource_toml["tps"])
        path_to_resource = resource_toml["path_to_resource"]

        _check_range(resource_tps, 0, float("inf"))

        current_resource = None

        if resource_type == AWS_LAMBDA_FUNCTION:
            resource_duration = int(resource_toml["duration"])
            _check_range(resource_duration, 0, 900000)
            current_resource = _generate_lambda_function(
                resource_type,
                resource_name,
                resource_object,
                resource_tps,
                resource_duration,
                path_to_resource,
            )
            key = str(resource_toml["key"])
            self._graph.resources_to_analyze[key] = current_resource

        elif resource_type == AWS_APIGATEWAY_RESTAPI:
            current_resource = _generate_api_gateway(
                resource_type,
                resource_name,
                resource_object,
                resource_tps,
                path_to_resource,
            )
        elif resource_type == AWS_DYNAMODB_TABLE:
            current_resource = _generate_dynamo_db_table(
                resource_type,
                resource_name,
                resource_object,
                resource_tps,
                path_to_resource,
            )
        else:
            raise ValueError("invalid type")

        for child_toml in resource_children:
            child_resource = self._parse_single_resource_toml(child_toml, False)
            current_resource.children.append(child_resource)

        if is_entry_point:
            self._graph.entry_points.append(current_resource)
        else:
            return current_resource

        return None

    def generate_graph_from_toml(self, config_file: Any) -> CheckGraph:
        """
        Generates the graph from the toml data

        Args:
            config_file: Any
                The samconfig.toml file

        Raises:
            TypeError
                Raises an error if a value is of a non-expected type
            tomlkit.exceptions.NonExistentKey
                Raises an error if an expected key does not exist
            ValueError
                Raises an error if a value is of a non-expected type

        Returns:
            _graph: CheckGraph
                Returns the generated graph
        """
        try:
            self._graph_toml = _get_data_from_toml(config_file)

            self._parse_toml_lambda_function_info()
            self._parse_resources()
        except TypeError as exception:
            LOG.error(
                "ERROR: A value in samconfig.toml was changed to an unexpected value type. Please undo all changes in "
                "the samconfig.toml file, or go through the sam check guided process again to re-write the data in "
                "samconfig.toml."
            )
            raise exception
        except tomlkit.exceptions.NonExistentKey as exception:
            LOG.error(
                "ERROR: a key value was changed in samconfig.toml. Please undo all changes in the samconfig.toml file,"
                " or go through the sam check guided process again to re-write the data in samconfig.toml."
            )
            raise exception

        except ValueError as exception:
            exception_type = exception.args[0]
            if exception_type == "invalid type":
                LOG.error(
                    "ERROR: An incorrect resource type was detected. Please undo all changes in the samconfig.toml "
                    "file, or go through the sam check guided process again to re-write the data in samconfig.toml."
                )
            elif exception_type == "invalid number":
                LOG.error(
                    "ERROR: A value was outside of the accepted range. Please undo all changes in the samconfig.toml "
                    "file, or go through the sam check guided process again to re-write the data in samconfig.toml."
                )
            elif exception_type == "invalid unit":
                LOG.error(
                    "ERROR: An invalid memory unit was detected. Please undo all changes in the samconfig.toml file,"
                    " or go through the sam check guided process again to re-write the data in samconfig.toml."
                )

            raise exception

        return self._graph


def _check_pricing_info(lambda_function_pricing: LambdaFunctionPricing):
    """
    Chewcks all priocing info to ensure it is of the expected type and value

    Parameters
    ----------
        lambda_function_pricing: LambdaFunctionPricing):
            The lambda function pricing object

    Raises:
        ValueError
            Raises an error if a value is not valid
    """
    number_of_requests = lambda_function_pricing.number_of_requests
    average_duration = lambda_function_pricing.average_duration
    allocated_memory = lambda_function_pricing.allocated_memory
    allocated_memory_unit = lambda_function_pricing.allocated_memory_unit

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

    _check_range(number_of_requests, min_requests, float("inf"))
    _check_range(average_duration, min_duration, max_duration)
    _check_range(allocated_memory, min_memory, max_memory)


def _check_range(check_value: int, min_value: int, max_value: int):
    """
    Checks the range if the provided input with the allowed max and min values

    Parameters
    ----------
        check_value: int
            The value to check if it's within the range
        min_value: int
            The minimum allowed value
        max_value: int
            The maximum allowed value

    Raises:
        ValueError
            Raises an error if a value is outside of the allowed range
    """
    if check_value < min_value or check_value > max_value:
        raise ValueError("invalid number")


def _get_data_from_toml(config_file: Any) -> Dict:
    """
    Gets all of the necessary data from the samconfig.toml file

    Paremeters
    ----------
        config_file: Any
            The samconfig.toml file

    Returns
    -------
        dict
            Returns one large dict containing all of the sam check data
            from the samconfig.toml file
    """
    samconfig = get_config_ctx(config_file)

    return samconfig.get_all(["load"], "graph", "check")["all_graph_data"]


def _generate_lambda_function(
    resource_type: str,
    resource_name: str,
    resource_object: Dict,
    resource_tps: int,
    resource_duration: int,
    path_to_resource: List[str],
) -> LambdaFunction:
    """
    Generates a lambda function object

    Parameters
    ----------
        resource_type: str
            The resource type
        resource_name: str
            The resource name
        resource_object: Dict
            The resource object that was retrieved from the template when it was first parsed
        resource_tps: int
            The resource tps
        resource_duration: int
            The resource duration
        path_to_resource: List[str]
            The path taken to get to this state of the resource

    Returns
    -------
        lambda_function: LambdaFunction
            Returns a generated lambda function object
    """
    lambda_function = LambdaFunction(resource_object, resource_type, resource_name, path_to_resource)
    lambda_function.duration = resource_duration
    lambda_function.tps = resource_tps

    return lambda_function


def _generate_api_gateway(
    resource_type: str,
    resource_name: str,
    resource_object: Dict,
    resource_tps: int,
    path_to_resource: List[str],
) -> ApiGateway:
    """
    Generates an ApiGateway object

    Parameters
    ----------
        resource_type: str
            The resource type
        resource_name: str
            The resource name
        resource_object: Dict
            The resource object that was retrieved from the template when it was first parsed
        resource_tps: int
            The resource tps
        path_to_resource: List[str]
            The path taken to get to this state of the resource

    Returns
    -------
        api_gateway: ApiGateway
            Retruns a generated ApiGateway object
    """
    api_gateway = ApiGateway(resource_object, resource_type, resource_name, path_to_resource)
    api_gateway.tps = resource_tps

    return api_gateway


def _generate_dynamo_db_table(
    resource_type: str,
    resource_name: str,
    resource_object: Dict,
    resource_tps: int,
    path_to_resource: List[str],
) -> DynamoDB:
    """
    Generates a DynamoDB object

    Parameters
    ----------
        resource_type: str
            The resource type
        resource_name: str
            The resource name
        resource_object: Dict
            The resource object that was retrieved from the template when it was first parsed
        resource_tps: int
            The resource tps
        path_to_resource: List[str]
            The path taken to get to this state of the resource

    Returns
    -------
        dynamo_db_table: DynamoDB
            Returns a generated DynamoDB object
    """
    dynamo_db_table = DynamoDB(resource_object, resource_type, resource_name, path_to_resource)
    dynamo_db_table.tps = resource_tps

    return dynamo_db_table
