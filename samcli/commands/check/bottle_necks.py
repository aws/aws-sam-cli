"""
Bottle neck questions are asked here. Data is saved in graph, but not calcualted here.
"""
from typing import List, Union
import click

from samcli.commands.check.resources.dynamo_db import DynamoDB
from samcli.commands.check.resources.lambda_function import LambdaFunction
from samcli.commands.check.resources.api_gateway import ApiGateway
from samcli.commands.check.resources.graph import CheckGraph
from samcli.commands.check.resources.pricing import CheckPricing

from samcli.commands._utils.resources import AWS_LAMBDA_FUNCTION

from samcli.commands.check.lib.ask_question import ask


class BottleNecks:
    _graph: CheckGraph
    _lambda_max_duration: int
    _pricing: CheckPricing

    def __init__(self, graph: CheckGraph):
        """
        Parameters
        ----------
            graph: CheckGraph
                The graph object. This is where all of the data is stored
        """
        self._graph = graph
        self._lambda_max_duration = 900000
        self._pricing = CheckPricing(graph)

    def ask_entry_point_question(self) -> None:
        """
        User is asked which entry point they'd like to start with
        """
        entry_points = self._graph.entry_points
        entry_point_holder = []

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
            current_entry_point_name = current_entry_point.resource_name
            entry_point_holder.append(current_entry_point)

            self._ask_bottle_neck_questions(current_entry_point, current_entry_point_name)

            click.echo("")

        for entry_point in entry_point_holder:
            self._graph.entry_points.append(entry_point)

    def _ask_bottle_neck_questions(
        self,
        resource: Union[LambdaFunction, ApiGateway, DynamoDB],
        entry_point_name: str,
        previous_resource_name: str = "",
        current_path=None,
    ) -> None:
        """Specific bottle neck questions are asked based on resource type

        Parameters
        ----------
            resource: Union[LambdaFunction, ApiGateway, DynamoDB]
                The current lambda function object being analyzed from the graph
            entry_point_name: str
                Entry point resource name
            previous_resource_name: str
                The parent resource to the current one being analyzed
            current_path: List[str]
                The current path being followed
        """

        if not current_path:
            current_path = []

        resource.entry_point_resource = entry_point_name
        if resource.resource_type == AWS_LAMBDA_FUNCTION:
            self.lambda_bottle_neck_quesitons(resource, entry_point_name, previous_resource_name, current_path)
        else:
            self.event_source_bottle_neck_questions(resource, entry_point_name, previous_resource_name, current_path)

    def event_source_bottle_neck_questions(
        self,
        event_source: Union[ApiGateway, DynamoDB],
        entry_point_name: str,
        previous_resource_name: str,
        current_path: List[str],
    ) -> None:
        """
        If an event source does not have any child nodes, then this event source is not a parent to any
        lambda functions. This can only happen if a lambda function has permissions to access a specific resource,
        but that resource does not access its own lambda function.
        For example: a lambda function may have permission to write to a dynamoDB table, but that table is
        not an event to some other lambda function.
        If that's the case, no further bottle neck questions are needed to be asked, since bottle necks
        are currently only determined at the lambda function, and not the event source itself

        If the event source is an entry point, proceed normally. If it is not an entry point (i.e. a lambda
        function calls this resource), its tps will be limited by the entry point that lead to this resource.

        Parameters
        ----------
            event_source: Union[ApiGateway, DynamoDB]
                The current event source to ask bottle neck questions about
            entry_point_name: str
                The entry point name to teh current event source. Can be None
            previous_resource_name: str
                The direct parent resource to the current one. Can be None
            current_path: List[str]
                The current path to the given event source
        """
        if event_source.children == []:
            return

        user_input_tps = ask(
            "What is the expected per-second arrival rate for [%s]?\n[TPS]" % (event_source.resource_name)
        )
        event_source.tps = user_input_tps

        if previous_resource_name:
            # i.e. this current reource is not an entry point resource
            event_source.path_to_resource = current_path[:]
            event_source.path_to_resource.append(previous_resource_name)

        for child in event_source.children:
            child.tps = user_input_tps
            self._ask_bottle_neck_questions(
                child, entry_point_name, event_source.resource_name, event_source.path_to_resource
            )

    def lambda_bottle_neck_quesitons(
        self,
        lambda_function: LambdaFunction,
        entry_point_name: str,
        previous_resource_name: str,
        current_path: List[str],
    ) -> None:
        """
        Bottleneck quesitons for lambda functions

        Parameters
        ----------
            lambda_function: LambdaFunction
                The current lambda function object to ask bottle neck questions on
            entry_point_name: str
                The name of the entry point resource
            previous_resource_name: str
                Parent reource of current resource
            current_path: List[str]
                The current path being followed
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

        if previous_resource_name:
            # i.e. this current reource is not an entry point resource
            lambda_function.path_to_resource = current_path[:]
            lambda_function.path_to_resource.append(previous_resource_name)

        # This given instance of a lambda function is what needs to be analyzed.
        copied_lambda_function = lambda_function.copy_data()

        # To ensure the correct object (not the one in the graph) is saved to the samconfig file,
        # the copied object will need to be found at a later stage. Putting it in a dictionary
        # will enable it to be found based on its name (which does not changes from the original
        # to the copied) and the name of the entry point (which is what makes the instance
        # unique).

        key = copied_lambda_function.resource_name + ":" + entry_point_name
        # Only the lambda functions can be the source of bottle necks for now.
        self._graph.resources_to_analyze[key] = copied_lambda_function

        self._pricing.ask_pricing_questions()

        for child in lambda_function.children:
            self._ask_bottle_neck_questions(
                child, entry_point_name, lambda_function.resource_name, lambda_function.path_to_resource
            )
