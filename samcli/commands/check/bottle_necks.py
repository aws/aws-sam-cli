import click

from click import confirm
from click import prompt

from .resources.Pricing import Pricing


class BottleNecks:
    def __init__(self, graph):
        self.graph = graph
        self.pricing = Pricing(graph)

    def ask(self, question, min=1, max=float("inf")):
        valid_user_input = False
        user_input = None
        while valid_user_input is False:
            user_input = click.prompt(text=question, type=int)
            if user_input > max or user_input < min:
                click.echo("Please enter a number within the range")
            else:
                valid_user_input = True

        return user_input

    def ask_entry_point_question(self):
        entry_points = self.graph.get_entry_points()

        # All entry points must be calcualted before info can be displayed
        while entry_points != []:
            entry_point_question = (
                "We found the following resources in your application that could be the entry point for a request."
            )
            item_number = 1
            for item in entry_points:
                item_name = item.get_name()
                entry_point_question += "\n[%i] %s" % (item_number, item_name)
                item_number += 1

            entry_point_question += "\nWhere should the simulation start?"
            user_input = self.ask(entry_point_question, 1, item_number - 1)

            click.echo("")

            current_entry_point = entry_points.pop(user_input - 1)

            self.ask_bottle_neck_questions(current_entry_point)

            click.echo("")

        return

    def ask_bottle_neck_questions(self, resource):
        if resource.get_resource_type() == "AWS::Lambda::Function":
            self.lambda_bottle_neck_quesitons(resource)
        else:
            self.event_source_bottle_neck_questions(resource)

    def event_source_bottle_neck_questions(self, event_source):
        user_input_tps = self.ask(
            "What is the expected per-second arrival rate for [%s]?\n[TPS]" % (event_source.get_name())
        )
        event_source.set_tps(user_input_tps)

        for child in event_source.get_children():
            child.set_tps(user_input_tps)
            self.ask_bottle_neck_questions(child)

    def lambda_bottle_neck_quesitons(self, lambda_function):
        # If there is no entry point to the lambda function, get tps
        if lambda_function.get_tps() is None:
            user_input_tps = self.ask(
                "What is the expected per-second arrival rate for [%s]?\n[TPS]" % (lambda_function.get_name())
            )
            lambda_function.set_tps(user_input_tps)

        user_input_duration = self.ask(
            "What is the expected duration for the Lambda function [%s] in ms?\n[1 - 900,000]"
            % (lambda_function.get_name()),
            1,
            900000,
        )

        lambda_function.set_duration(user_input_duration)

        self.pricing.ask_pricing_question(lambda_function)

        # Only the lambda functions can be the source of bottle necks for now.
        self.graph.add_resource_to_analyze(lambda_function)

        for child in lambda_function.get_children():
            self.ask_bottle_neck_questions(child)
