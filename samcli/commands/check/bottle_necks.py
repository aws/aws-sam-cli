"""
Bottle neck questions are asked here. Data is saved in graph, but not calcualted here.
"""
import click

from samcli.commands.check.resources.graph import CheckGraph
from samcli.commands.check.resources.lambda_function import LambdaFunction
from samcli.commands._utils.resources import AWS_LAMBDA_FUNCTION

from samcli.commands.check.lib.ask_question import ask


class BottleNecks:
    _graph: CheckGraph
    _lambda_max_duration: int

    def __init__(self, graph: CheckGraph):
        """
        Parameters
        ----------
            graph: CheckGraph
                The graph object. This is where all of the data is stored
        """
        self._graph = graph
        self._lambda_max_duration = 900000

    def ask_entry_point_question(self) -> None:
        """
        User is asked which entry point they'd like to start with
        """
        entry_points = self._graph.entry_points

        # All entry points must be calcualted before info can be displayed
        while entry_points:
            entry_point_question = (
                "We found the following resources in your application that could be the entry point for a request."
            )

            item_number = 0

            for item_number, item in enumerate(entry_points):
                item_name = item.resource_name
                entry_point_question += "\n[%i] %s" % (item_number + 1, item_name)

            entry_point_question += "\nWhere should the simulation start?"

            user_input = ask(entry_point_question, 1, item_number + 1)
            current_entry_point = entry_points.pop(user_input - 1)

            self._ask_bottle_neck_questions(current_entry_point)
            self._graph.resources_to_analyze.append(current_entry_point)

            click.echo("")

    def _lambda_bottle_neck_quesitons(self, lambda_function: LambdaFunction) -> None:
        """
        TPS (if necessary) and duration questions are asked for lambda functions

        Parameters
        ----------
            lambda_function: LambdaFunction
                The current lambda function object being analyzed from the graph
        """
        # If there is no entry point to the lambda function, get tps
        if lambda_function.tps == -1:

            user_input_tps = ask(
                "What is the expected per-second arrival rate for [%s]?\n[TPS]" % (lambda_function.resource_name)
            )
            lambda_function.tps = user_input_tps

        user_input_duration = ask(
            "What is the expected duration for the Lambda function [%s] in ms?\n[1 - %i]"
            % (lambda_function.resource_name, self._lambda_max_duration),
            1,
            self._lambda_max_duration,
        )

        lambda_function.duration = user_input_duration

    def _ask_bottle_neck_questions(self, resource: LambdaFunction) -> None:

        """Specific bottle neck questions are asked based on resource type

        Parameters
        ----------
            resource: LambdaFunction
                The current lambda function object being analyzed from the graph
        """
        if resource.resource_type == AWS_LAMBDA_FUNCTION:
            self._lambda_bottle_neck_quesitons(resource)
