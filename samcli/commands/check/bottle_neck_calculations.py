"""
Class for doing all bottle neck calcualtions on all resources
"""
from typing import List
import boto3
import click
from samcli.commands.check.resources.warning import CheckWarning
from samcli.commands.check.resources.graph import CheckGraph

from samcli.commands._utils.resources import AWS_LAMBDA_FUNCTION


class BottleNeckCalculations:
    _graph: CheckGraph
    _template_path: str

    def __init__(self, graph: CheckGraph, template_path: str):
        self._graph = graph
        self._template_path = template_path

    def _get_error_file_lines(self, resource_name: str) -> str:
        """
        Finds the current resource in the template file. Adds a few of the lines
        from the file to the warning message.

        Parameters
        ----------
            resource_name: str
                The resource name to find in the file

        Returns
        -------
            error_file_lines: str
                The error message showing where in the file the bottle neck
                is located
        """
        error_file_lines = "\nThe resource [%s] can be found here...\n  --> %s\n" % (resource_name, self._template_path)

        error_file_lines += "   |\n"

        with open(self._template_path, "r", encoding="utf-8") as file:
            content = [line.strip("\n") for line in file.readlines()]

            resource_pos = -1
            resource_to_find = resource_name + ":"
            found_resource = False

            for pos, file_line in enumerate(content):
                if file_line.strip() == resource_to_find:
                    resource_pos = pos
                    found_resource = True
                    break

            if not found_resource:
                return ""

            for current_pos in range(resource_pos, resource_pos + 4):
                if current_pos >= len(content):
                    break

                if current_pos is resource_pos:
                    error_file_lines += "%i |" % (current_pos + 1) + content[current_pos] + "\n"
                else:
                    error_file_lines += "   |" + content[current_pos] + "\n"

        return error_file_lines

    def _generate_warning_message(
        self,
        capacity_used: int,
        resource_name: str,
        concurrent_executions: int,
        duration: int,
        tps: int,
        burst_concurrency: int,
        path_to_resource: List[str],
    ):
        """
        Generates a warning message based on the severity of the bottle neck

        Parameters
        ----------
            capacity_used: int
                Total capacity used as a percentage
            resource_name: str
                Current resource name
            concurrent_executions: int
                Total amount of concurrent executions allowed
            duration: int
                Duration of current resource
            tps: int
                TPS of current resource
            burst_concurrency: int
                Total allowed burst concurrency allowed
            path_to_resource: List[str]
                Path taken to get to current resource
        """

        path_str = _generate_path_string(path_to_resource)

        if capacity_used <= 70:
            message = (
                "For the lambda function [%s], following the path [%s], you will not be close to its soft "
                "limit of %i concurrent executions." % (resource_name, path_str, concurrent_executions)
            )
            warning = CheckWarning(message)
            self._graph.green_warnings.append(warning)

        elif capacity_used < 90:
            message = (
                "For the lambda function [%s], following the path [%s], the %ims duration and %iTPS arrival "
                "rate is using %i%% of the allowed concurrency on AWS Lambda. A limit increase should be considered:"
                "\nhttps://console.aws.amazon.com/servicequotas"
                % (resource_name, path_str, duration, tps, round(capacity_used))
            )
            warning = CheckWarning(message)
            self._graph.yellow_warnings.append(warning)

        elif capacity_used <= 100:
            message = (
                "For the lambda function [%s], following the path [%s], the %ims duration and %iTPS "
                "arrival rate is using %i%% of the allowed concurrency on AWS Lambda. It is very close to "
                "the limits of the lambda function. It is strongly recommended that you get a limit "
                "increase before deploying your application:"
                "\nhttps://console.aws.amazon.com/servicequotas"
                % (resource_name, path_str, duration, tps, round(capacity_used))
            )
            warning = CheckWarning(message)
            self._graph.red_warnings.append(warning)

        else:  # capacity_used > 100
            burst_capacity_used = _check_limit(tps, duration, burst_concurrency)
            message = (
                "For the lambda function [%s], following the path [%s], the %ims duration and %iTPS arrival "
                "rate is using %i%% of the allowed concurrency on AWS Lambda. It exceeds the limits of the "
                "lambda function. It will use %i%% of the available burst concurrency. It is strongly "
                "recommended that you get a limit increase before deploying your application:"
                "\nhttps://console.aws.amazon.com/servicequotas"
                % (resource_name, path_str, duration, tps, round(capacity_used), round(burst_capacity_used))
            )

            message += self._get_error_file_lines(resource_name)

            warning = CheckWarning(message)
            self._graph.red_burst_warnings.append(warning)

    def run_calculations(self):
        """
        Runs calculaitons for each resource
        """
        click.echo("Running calculations...")

        for resource in self._graph.resources_to_analyze.values():
            resource_type = resource.resource_type
            resource_name = resource.resource_name
            resource_path = resource.path_to_resource

            if resource_type == AWS_LAMBDA_FUNCTION:

                client = boto3.client("service-quotas")
                burst_concurrency = client.get_aws_default_service_quota(ServiceCode="lambda", QuotaCode="L-548AE339")[
                    "Quota"
                ]["Value"]
                concurrent_executions = client.get_aws_default_service_quota(
                    ServiceCode="lambda", QuotaCode="L-B99A9384"
                )["Quota"]["Value"]

                tps = resource.tps
                duration = resource.duration
                capacity_used = _check_limit(tps, duration, concurrent_executions)

                self._generate_warning_message(
                    capacity_used, resource_name, concurrent_executions, duration, tps, burst_concurrency, resource_path
                )


def _check_limit(tps: int, duration: int, execution_limit: int):
    """
    Checks the limit of the current resource

    Parameters
    ----------
        tps: int
            TPS of current resource
        duration: int
            Duration of current resource
        execution_limit: int
            Execution limit of current resource type

    Returns
    -------
        float
            Returns the percentage of the amount of executions used
    """
    tps_max_limit = (1000 / duration) * execution_limit
    return (tps / tps_max_limit) * 100


def _generate_path_string(path_list: List[str]):
    path_str = ""

    for counter, item in enumerate(path_list):
        path_str += item

        if counter < len(path_list) - 1:
            path_str += " --> "

    return path_str
