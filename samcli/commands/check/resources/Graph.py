"""
Class for graph. All data is stored in the graph directly, or within nodes that are stored in the graph
"""
from typing import List
from samcli.commands.check.resources.LambdaFunction import LambdaFunction


class Graph:
    def __init__(self):
        self._entry_points: List = []
        self._resources_to_analyze: List = []

    @property
    def entry_points(self) -> List:
        return self._entry_points

    @entry_points.setter
    def entry_points(self, node: LambdaFunction):
        self._entry_points.append(node)

    @property
    def resources_to_analyze(self) -> List:
        return self._resources_to_analyze

    @resources_to_analyze.setter
    def resources_to_analyze(self, resource: LambdaFunction):
        self._resources_to_analyze.append(resource)

    def generate(self, lambda_functions: List):
        # Find all entry points
        for function in lambda_functions:
            if not function.parents:  # No parent resourecs, so this is an entry point
                self.entry_points.append(function)
