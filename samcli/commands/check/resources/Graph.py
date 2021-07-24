"""
Class for graph. All data is stored in the graph directly, or within nodes that are stored in the graph
"""
from typing import Any
from samcli.commands.check.resources.LambdaFunction import LambdaFunction

from logging import warn



class Graph:
    def __init__(self):
        self._entry_points = []
        self._resources_to_analyze = []
        self.entry_points = []
        self.resources_to_analyze = []
        self.green_warnings = []
        self.yellow_warnings = []
        self.red_warnings = []
        self.red_burst_warnings = []


    @property
    def entry_points(self) -> Any:
        return self._entry_points

    @entry_points.setter
    def entry_points(self, node: LambdaFunction):
        self._entry_points.append(node)

    @property
    def resources_to_analyze(self) -> Any:
        return self._resources_to_analyze


    @resources_to_analyze.setter
    def resources_to_analyze(self, resource: LambdaFunction):
        self._resources_to_analyze.append(resource)

    def add_green_warning(self, warning):
        self.green_warnings.append(warning)

    def get_green_warnings(self):
        return self.green_warnings

    def add_yellow_warning(self, warning):
        self.yellow_warnings.append(warning)

    def get_yellow_warnings(self):
        return self.yellow_warnings

    def add_red_warning(self, warning):
        self.red_warnings.append(warning)

    def get_red_warnings(self):
        return self.red_warnings

    def add_red_burst_warning(self, warning):
        self.red_burst_warnings.append(warning)

    def get_red_burst_warnings(self):
        return self.red_burst_warnings

