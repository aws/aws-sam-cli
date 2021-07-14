from types import resolve_bases
import click
from .resources.Warning import Warning

import boto3


class BottleNeckCalculations:
    def __init__(self, graph):
        self.graph = graph

    def generate_warning_message(
        self, capacity_used, resource_name, concurrent_executions, duration, tps, burst_concurrency
    ):
        warning = Warning()

        if capacity_used <= 70:
            warning.set_message(
                "For the lambda function [%s], you will not be close to its soft limit of %i concurrent executions."
                % (resource_name, concurrent_executions)
            )
            self.graph.add_green_warning(warning)

        elif capacity_used > 70 and capacity_used < 90:
            warning.set_message(
                "For the lambda function [%s], the %ims duration and %iTPS arrival rate is using %i%% of the allowed concurrency on AWS Lambda. A limit increase should be considered:\nhttps://console.aws.amazon.com/servicequotas"
                % (resource_name, duration, tps, round(capacity_used))
            )
            self.graph.add_yellow_warning(warning)

        elif capacity_used >= 90 and capacity_used <= 100:
            warning.set_message(
                "For the lambda function [%s], the %ims duration and %iTPS arrival rate is using %i%% of the allowed concurrency on AWS Lambda. It is very close to the limits of the lambda function. It is strongly recommended that you get a limit increase before deploying your application:\nhttps://console.aws.amazon.com/servicequotas"
                % (resource_name, duration, tps, round(capacity_used))
            )
            self.graph.add_red_warning(warning)

        else:  # capacity_used > 100
            burst_capacity_used = self.check_limit(tps, duration, burst_concurrency)
            warning.set_message(
                "For the lambda function [%s], the %ims duration and %iTPS arrival rate is using %i%% of the allowed concurrency on AWS Lambda. It exceeds the limits of the lambda function. It will use %i%% of the available burst concurrency. It is strongly recommended that you get a limit increase before deploying your application:\nhttps://console.aws.amazon.com/servicequotas"
                % (resource_name, duration, tps, round(capacity_used), round(burst_capacity_used))
            )
            self.graph.add_red_burst_warning(warning)

    def run_calculations(self):
        click.echo("Running calculations...")

        for resource in self.graph.get_resources_to_analyze():
            resource_type = resource.get_resource_type()
            resource_name = resource.get_name()

            if resource_type == "AWS::Lambda::Function":

                client = boto3.client("service-quotas")
                burst_concurrency = client.get_aws_default_service_quota(ServiceCode="lambda", QuotaCode="L-548AE339")[
                    "Quota"
                ]["Value"]
                concurrent_executions = client.get_aws_default_service_quota(
                    ServiceCode="lambda", QuotaCode="L-B99A9384"
                )["Quota"]["Value"]

                tps = resource.get_tps()
                duration = resource.get_duration()
                capacity_used = self.check_limit(tps, duration, concurrent_executions)

                self.generate_warning_message(
                    capacity_used, resource_name, concurrent_executions, duration, tps, burst_concurrency
                )

    def check_limit(self, tps, duration, execution_limit):
        tps_max_limit = (1000 / duration) * execution_limit
        return (tps / tps_max_limit) * 100
