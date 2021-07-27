"""
Class for graph. All data is stored in the graph directly, or within nodes that are stored in the graph
"""
from typing import List


class Graph:
    entry_points: List
    resources_to_analyze: List

    def __init__(self):
        self.entry_points: List = []
        self.resources_to_analyze: List = []

    def generate(self, lambda_functions: List) -> None:
        """Generates the graph based on the connections calulated
        Args:
            lambda_functions (List): List of all lambda functions in template
        """
        # Find all entry points
        for function in lambda_functions:
            if not function.parents:  # No parent resourecs, so this is an entry point
                self.entry_points.append(function)
