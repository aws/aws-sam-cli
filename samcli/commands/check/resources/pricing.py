"""
Pricing questions are asked here. Pricing is only done for
Lambda Functions as of now. Data is stored in graph in
Lambda function pricing object.
"""

import click

from samcli.commands.check.resources.graph import CheckGraph
from samcli.commands.check.resources.lambda_function_pricing import LambdaFunctionPricing
from samcli.commands._utils.resources import AWS_LAMBDA_FUNCTION


class CheckPricing:
    _graph: CheckGraph

    def __init__(self, graph: CheckGraph) -> None:
        """
        Parameters
        ----------
            graph: CheckGraph
              The graph object. This is where all of the data is stored
        """
        self._graph = graph
        self._asked_lambda_questions = False

    def ask_pricing_questions(self) -> None:
        """
        Pricing quetions for various resources get asked here
        Pricing is only done for Lambda functions now
        """

        for resource in self._graph.resources_to_analyze.values():
            # Only ask lambda quetions once for all lambda functions
            if resource.resource_type == AWS_LAMBDA_FUNCTION and not self._asked_lambda_questions:
                click.echo("Pricing Questions")
                self._asked_lambda_questions = True
                lambda_pricing = LambdaFunctionPricing()
                lambda_pricing.ask_lambda_function_questions()

                self._graph.unique_pricing_info["LambdaFunction"] = lambda_pricing
