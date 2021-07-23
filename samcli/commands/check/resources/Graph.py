"""
Class for graph. All data is stored in the graph directly, or within nodes that are stored in the graph
"""
from typing import Any
from samcli.commands.check.resources.LambdaFunction import LambdaFunction


class Graph:
    def __init__(self):
        self._entry_points = []
        self._resources_to_analyze = []

    def add_entry_point(self, node: LambdaFunction):
        self._entry_points.append(node)

    def get_entry_points(self) -> Any:
        return self._entry_points

    def get_resources_to_analyze(self) -> Any:
        return self._resources_to_analyze

    def add_resource_to_analyze(self, resource: LambdaFunction):
        self._resources_to_analyze.append(resource)
