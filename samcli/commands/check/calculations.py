"""
Bottle neck calculations are done here. Warning messages are also generated here
"""
import click
import boto3
from samcli.commands._utils.resources import AWS_LAMBDA_FUNCTION
from samcli.commands.check.resources.Graph import Graph
from .resources.Warning import CheckWarning


class Calculations:
    def __init__(self, graph: Graph):
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
        warning = CheckWarning()

        if capacity_used <= 70:
            warning.message = (
                "For the lambda function [%s], you will not be close to its soft limit of %i concurrent executions."
                % (resource_name, concurrent_executions)
            )
            self._graph.green_warnings.append(warning)

        elif capacity_used > 70 and capacity_used < 90:
            warning.message = (
                "For the lambda function [%s], the %ims duration and %iTPS arrival rate is using %i%% of the allowed concurrency on AWS Lambda. A limit increase should be considered:\nhttps://console.aws.amazon.com/servicequotas"
                % (resource_name, duration, tps, round(capacity_used))
            )
            self._graph.yellow_warnings.append(warning)

        elif capacity_used >= 90 and capacity_used <= 100:
            warning.message = (
                "For the lambda function [%s], the %ims duration and %iTPS arrival rate is using %i%% of the allowed concurrency on AWS Lambda. It is very close to the limits of the lambda function. It is strongly recommended that you get a limit increase before deploying your application:\nhttps://console.aws.amazon.com/servicequotas"
                % (resource_name, duration, tps, round(capacity_used))
            )
            self._graph.red_warnings.append(warning)

        else:  # capacity_used > 100
            burst_capacity_used = self._check_limit(tps, duration, burst_concurrency)
            warning.message = (
                "For the lambda function [%s], the %ims duration and %iTPS arrival rate is using %i%% of the allowed concurrency on AWS Lambda. It exceeds the limits of the lambda function. It will use %i%% of the available burst concurrency. It is strongly recommended that you get a limit increase before deploying your application:\nhttps://console.aws.amazon.com/servicequotas"
                % (resource_name, duration, tps, round(capacity_used), round(burst_capacity_used))
            )
            self._graph.red_burst_warnings.append(warning)

    def run_bottle_neck_calculations(self):
        click.echo("Running calculations...")

        for resource in self._graph.resources_to_analyze:
            resource_type = resource.resource_type
            resource_name = resource.resource_name

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
                capacity_used = self._check_limit(tps, duration, concurrent_executions)

                self._generate_warning_message(
                    capacity_used, resource_name, concurrent_executions, duration, tps, burst_concurrency
                )

    def _check_limit(self, tps: int, duration: int, execution_limit: int) -> float:
        tps_max_limit = (1000 / duration) * execution_limit
        return (tps / tps_max_limit) * 100
