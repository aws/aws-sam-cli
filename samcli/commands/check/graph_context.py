"""
This class will generate the graph based on the template data.
Connections between nodes will occur here.
"""
from typing import List
from .resources.Graph import Graph


class GraphContext:
    def __init__(self, lambda_functions: List):
        self._lambda_functions = lambda_functions

    def generate(self) -> Graph:
        graph = Graph()

        # Find all entry points
        for function in self._lambda_functions:
            if not function.get_parents():  # No parent resourecs, so this is an entry point
                graph.add_entry_point(function)

        return graph
