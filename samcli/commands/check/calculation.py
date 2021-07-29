"""
Bottle neck calculations are done here. Warning messages are also generated here
"""
import click
import boto3
import botocore


from samcli.commands._utils.resources import AWS_LAMBDA_FUNCTION
from samcli.commands.check.resources.Graph import Graph
from .resources.Warning import CheckWarning


class Calculation:
    _graph: Graph

    def __init__(self, graph: Graph):
        """
        Args:
            graph (Graph): The graph object. This is where all of the data is stored
        """
        self._graph = graph

    def _generate_warning_message(
        self,
        capacity_used: int,
        resource_name: str,
        concurrent_executions: int,
        duration: int,
        tps: int,
        burst_concurrency: int,
    ):
        """Depending on how severe the bottle neck is, a different warning message will be generated
        Args:
            capacity_used (int): Percentage of capacity used
            resource_name (str): Recource name that the warning is for
            concurrent_executions (int): Concurrent executions based on users account
            duration (int): Duration of lambda function
            tps (int): TPS of lambda function based on its parent resource
            burst_concurrency (int): Burst concurrency based on users account
        """


        if capacity_used <= 70:
            message = (
                "For the lambda function [%s], you will not be close to its soft limit of %i concurrent executions."
                % (resource_name, concurrent_executions)
            )
            warning = CheckWarning(message)
            self._graph.green_warnings.append(warning)

        elif capacity_used < 90:
            message = (
                f"For the lambda function [{resource_name}], the {duration}ms duration and {tps}TPS arrival rate is "
                f"using {round(capacity_used)}% of the allowed concurrency on AWS Lambda. A limit increase should "
                "be considered:\nhttps://console.aws.amazon.com/servicequotas"
            )
            warning = CheckWarning(message)
            self._graph.yellow_warnings.append(warning)

        elif capacity_used <= 100:
            message = (
                f"For the lambda function [{resource_name}], the {duration}ms duration and {tps}TPS arrival rate is "
                f"using {round(capacity_used)}% of the allowed concurrency on AWS Lambda. It is very close to the "
                "limits of the lambda function. It is strongly recommended that you get a limit increase before "
                "deploying your application:\nhttps://console.aws.amazon.com/servicequotas"
            )
            warning = CheckWarning(message)
            self._graph.red_warnings.append(warning)

        else:  # capacity_used > 100
            burst_capacity_used = _check_limit(tps, duration, burst_concurrency)
            message = (
                f"For the lambda function [{resource_name}], the {duration}ms duration and {tps}TPS arrival rate "
                f"is using {round(capacity_used)}% of the allowed concurrency on AWS Lambda. It exceeds the "
                f"limits of the lambda function. It will use {round(burst_capacity_used)}% of the "
                "available burst concurrency. It is strongly recommended that you get a limit increase before "
                "deploying your application:\nhttps://console.aws.amazon.com/servicequotas"
            )
            warning = CheckWarning(message)
            self._graph.red_burst_warnings.append(warning)

    def run_bottle_neck_calculations(self):
        """
        Bottle neck calculations are calculated and stored in the graph
        """
        click.echo("Running calculations...")

        client = boto3.client("service-quotas")

        for resource in self._graph.resources_to_analyze:
            resource_type = resource.resource_type
            resource_name = resource.resource_name

            if resource_type == AWS_LAMBDA_FUNCTION:

                try:
                    burst_concurrency = client.get_aws_default_service_quota(
                        ServiceCode="lambda", QuotaCode="L-548AE339"
                    )["Quota"]["Value"]
                    concurrent_executions = client.get_aws_default_service_quota(
                        ServiceCode="lambda", QuotaCode="L-B99A9384"
                    )["Quota"]["Value"]
                except botocore.exceptions.ClientError as error:
                    raise error

                except botocore.exceptions.ParamValidationError as error:
                    raise ValueError("The parameters you provided are incorrect: {}".format(error)) from error

                tps = resource.tps
                duration = resource.duration
                capacity_used = _check_limit(tps, duration, concurrent_executions)

                self._generate_warning_message(
                    capacity_used, resource_name, concurrent_executions, duration, tps, burst_concurrency
                )


def _check_limit(tps: int, duration: int, execution_limit: int) -> float:
    """The check to see if a given resource will cause a bottle neck.
    Args:
        tps (int): TPS of lambda function based on parent resource
        duration (int): Duration of lambda function
        execution_limit (int): Execution limit based on user account

    Returns:
        float: percentage of available concurrent executions used
    """
    tps_max_limit = (1000 / duration) * execution_limit
    return (tps / tps_max_limit) * 100
