from samcli.commands.check.resources.LambdaFunction import LambdaFunction
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
        entry_point_holder = []

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
            current_entry_point_name = current_entry_point.get_name()
            entry_point_holder.append(current_entry_point)

            self.ask_bottle_neck_questions(current_entry_point, current_entry_point_name)

            click.echo("")

        for entry_point in entry_point_holder:
            self.graph.add_entry_point(entry_point)

        return

    def ask_bottle_neck_questions(self, resource, entry_point_name):
        resource.entry_point_resource = entry_point_name
        if resource.get_resource_type() == "AWS::Lambda::Function":
            self.lambda_bottle_neck_quesitons(resource, entry_point_name)
        else:
            self.event_source_bottle_neck_questions(resource, entry_point_name)

    def event_source_bottle_neck_questions(self, event_source, entry_point_name):
        if event_source.get_children() == []:
            """
            If an event source does not have any child nodes, then this event source is not a parent to any
            lambda functions. This can only happen if a lambda function has permissions to access a specific resource,
            but that resource does not access its own lambda function.
            For example: a lambda function may have permission to write to a dynamoDB table, but that table is not an event
            to some other lambda function.
            If that's the case, no further bottle neck questions are needed to be asked, since bottle necks are currently
            only determined at the lambda function, and not the event source itself
            """
            return

        entry_point = True
        parent_tps = 0
        if event_source.get_parents():
            entry_point = False
            parent_tps = event_source.get_parents()[0].get_tps()

        """
        If the event source is an entry point, proceed normally. If it is not an entry point (i.e. a lambda function calls 
        this resource), its tps will be limited by the entry point that lead to this resource.
        """
        if entry_point:
            user_input_tps = self.ask(
                "What is the expected per-second arrival rate for [%s]?\n[TPS]" % (event_source.get_name())
            )
        else:
            user_input_tps = self.ask(
                "What is the expected per-second arrival rate for [%s]? [max: %i]\n[TPS]"
                % (event_source.get_name(), parent_tps),
                max=parent_tps,
            )
        event_source.set_tps(user_input_tps)

        for child in event_source.get_children():
            child.set_tps(user_input_tps)
            self.ask_bottle_neck_questions(child, entry_point_name)

    def lambda_bottle_neck_quesitons(self, lambda_function, entry_point_name):
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

        # This given instance of a lambda function is what needs to be analyzed.
        copied_lambda_function = lambda_function.copy_data()

        """
        To ensure the correct object (not the one in the graph) is saved to the samconfig file,
        the copied object will need to be found at a later stage. Putting it in a dictionary
        will enable it to be found based on its name (which does not changes from the original
        to the copied) and the name of the entry point (which is what makes the instance
        unique).
        """
        key = copied_lambda_function.resource_name + ":" + entry_point_name
        # Only the lambda functions can be the source of bottle necks for now.
        self.graph.resources_to_analyze[key] = copied_lambda_function

        for child in lambda_function.get_children():
            self.ask_bottle_neck_questions(child, entry_point_name)

