"""
Class for graph. All data is stored in the graph directly, or within nodes that are stored in the graph
"""
from typing import List
from samcli.commands.check.resources.LambdaFunction import LambdaFunction
from samcli.commands.check.resources.Warning import CheckWarning


class Graph:
    def __init__(self):
        self._entry_points: List = []
        self._resources_to_analyze: List = []
        self._green_warnings: List = []
        self._yellow_warnings: List = []
        self._red_warnings: List = []
        self._red_burst_warnings: List = []

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

    @property
    def green_warnings(self) -> List:
        return self._green_warnings

    @green_warnings.setter
    def green_warnings(self, warning: CheckWarning):
        self._green_warnings.append(warning)

    @property
    def yellow_warnings(self) -> List:
        return self._yellow_warnings

    @yellow_warnings.setter
    def yellow_warnings(self, warning: CheckWarning):
        self._yellow_warnings.append(warning)

    @property
    def red_warnings(self) -> List:
        return self._red_warnings

    @red_warnings.setter
    def red_warnings(self, warning: CheckWarning):
        self._red_warnings.append(warning)

    @property
    def red_burst_warnings(self) -> List:
        return self._red_burst_warnings

    @red_burst_warnings.setter
    def red_burst_warnings(self, warning: CheckWarning):
        self._red_burst_warnings.append(warning)
