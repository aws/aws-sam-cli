"""
This class will generate the graph based on the template data.
Connections between nodes will occur here.
"""
from typing import List
from .resources.Graph import Graph


class GraphContext:
    def __init__(self, lambda_functions: List):
        self.lambda_functions = lambda_functions

    def generate(self) -> Graph:
        graph = Graph()

        # Find all entry points
        for function in self.lambda_functions:
            if function.get_parents() == []:  # No parent resourecs, so this is an entry point
                graph.add_entry_point(function)
            else:
                pass

        return graph
