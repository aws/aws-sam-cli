"""
Pricing questions are asked here. Pricing is only done for
Lambda Functions as of now. Data is stored in graph in
Lambda function pricing object.
"""

import click

from samcli.commands.check.resources.graph import CheckGraph
from samcli.commands.check.resources.lambda_function_pricing import LambdaFunctionPricing
from samcli.commands._utils.resources import AWS_LAMBDA_FUNCTION


class Pricing:
    _graph: CheckGraph

    def __init__(self, graph: CheckGraph) -> None:
        """
        Args:
            graph (Graph): The graph object. This is where all of the data is stored

        - _max_num_requests are the maximum number of requests that the bulk API will accept
        - _min_memory_amount is the smallest amount of memory in MB that can be used to
          calcualte pricing info
        - _max_memory_amount is the largest amount of memory in MBthat can be used to
          calcualte pricing info
        - _max_duration is the maximum runtime for lambda funcitons in ms
        """
        self._graph: CheckGraph = graph

    def ask_pricing_questions(self) -> None:
        """
        Pricing quetions for various resources get asked here
        Pricing is only done for Lambda functions now
        """
        asked_lambda_questions = False
        click.echo("Pricing Questions")
        for resource in self._graph.resources_to_analyze:
            # Only ask lambda quetions once for all lambda functions
            if resource.resource_type == AWS_LAMBDA_FUNCTION and not asked_lambda_questions:
                asked_lambda_questions = True
                lambda_pricing = LambdaFunctionPricing()
                lambda_pricing.ask_lambda_function_questions()

                self._graph.lambda_function_pricing_info = lambda_pricing
