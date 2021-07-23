"""
Bottle neck questions are asked here. Data is saved in graph, but not calcualted here.
"""
import click

from samcli.commands.check.resources.LambdaFunction import LambdaFunction
from samcli.commands._utils.resources import AWS_LAMBDA_FUNCTION


class BottleNecks:
    def __init__(self, graph):
        self._graph = graph
        self._lambda_max_duration = 900000

    def ask_entry_point_question(self):
        entry_points = self._graph.get_entry_points()

        # All entry points must be calcualted before info can be displayed
        while entry_points:
            entry_point_question = (
                "We found the following resources in your application that could be the entry point for a request."
            )
            item_number = 1
            for item in entry_points:
                item_name = item.get_name()
                entry_point_question += "\n[%i] %s" % (item_number, item_name)
                item_number += 1

            entry_point_question += "\nWhere should the simulation start?"
            user_input = ask(entry_point_question, 1, item_number - 1)

            current_entry_point = entry_points.pop(user_input - 1)

            self.ask_bottle_neck_questions(current_entry_point)

            self._graph.add_resource_to_analyze(current_entry_point)

        click.echo("Running calculations...")

    def lambda_bottle_neck_quesitons(self, lambda_function: LambdaFunction):
        # If there is no entry point to the lambda function, get tps
        if lambda_function.get_tps() == -1:
            user_input_tps = ask(
                "What is the expected per-second arrival rate for [%s]?\n[TPS]" % (lambda_function.get_name())
            )
            lambda_function.set_tps(user_input_tps)

        user_input_duration = ask(
            "What is the expected duration for the Lambda function [%s] in ms?\n[1 - 900,000]"
            % (lambda_function.get_name()),
            1,
            self._lambda_max_duration,
        )

        lambda_function.set_duration(user_input_duration)

    def ask_bottle_neck_questions(self, resource: LambdaFunction):
        if resource.get_resource_type() == AWS_LAMBDA_FUNCTION:
            self.lambda_bottle_neck_quesitons(resource)


def ask(question: str, min_val=1, max_val=float("inf")) -> int:
    valid_user_input = False
    user_input = 0
    while not valid_user_input:
        user_input = click.prompt(text=question, type=int)
        if user_input > max_val or user_input < min_val:
            click.echo("Please enter a number within the range")
        else:
            valid_user_input = True

    return user_input
