"""
Bottle neck questions are asked here. Data is saved in graph, but not calcualted here.
"""
import click

from samcli.commands.check.resources.Graph import Graph
from samcli.commands.check.resources.LambdaFunction import LambdaFunction
from samcli.commands._utils.resources import AWS_LAMBDA_FUNCTION


class BottleNecks:
    _graph: Graph
    _lambda_max_duration: int

    def __init__(self, graph: Graph):
        """
        Args:
            graph (Graph): The graph object. This is where all of the data is stored
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
                item_number += 1

            entry_point_question += "\nWhere should the simulation start?"
            user_input = ask(entry_point_question, 1, item_number)

            current_entry_point = entry_points.pop(user_input - 1)

            self.ask_bottle_neck_questions(current_entry_point)

            self._graph.resources_to_analyze.append(current_entry_point)

        click.echo("Running calculations...")

    def _lambda_bottle_neck_quesitons(self, lambda_function: LambdaFunction) -> None:
        """
        TPS (if necessary) and duration questions are asked for lambda functions

        Args:
            lambda_function (LambdaFunction): [description]
        """
        # If there is no entry point to the lambda function, get tps
        if lambda_function.tps == -1:
            user_input_tps = ask(
                "What is the expected per-second arrival rate for [%s]?\n[TPS]" % (lambda_function.resource_name)
            )
            lambda_function.tps = user_input_tps

        user_input_duration = ask(
            "What is the expected duration for the Lambda function [%s] in ms?\n[1 - 900,000]"
            % (lambda_function.resource_name),
            1,
            self._lambda_max_duration,
        )

        lambda_function.duration = user_input_duration

    def ask_bottle_neck_questions(self, resource: LambdaFunction) -> None:
        """Specific bottle neck questions are asked based on resource type

        Args:
            resource (LambdaFunction): [description]
        """
        if resource.resource_type == AWS_LAMBDA_FUNCTION:
            self._lambda_bottle_neck_quesitons(resource)


def ask(question: str, min_val: int = 1, max_val: float = float("inf")) -> int:
    """Prompt the user for input based on provided range

    Args:
        question (str): The question to prompt the user with
        min_val (int, optional): Minimum acceptable value. Defaults to 1.
        max_val (float, optional): Maximum acceptable value. Defaults to float("inf").

    Returns:
        int: User selected value
    """
    valid_user_input = False
    user_input = 0
    while not valid_user_input:
        user_input = click.prompt(text=question, type=int)
        if user_input > max_val or user_input < min_val:
            click.echo("Please enter a number within the range")
        else:
            valid_user_input = True

    return user_input
