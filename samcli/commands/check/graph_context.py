from .resources.Graph import Graph


class GraphContext:
    def __init__(self, lambda_functions):
        self.lambda_functions = lambda_functions

    def generate(self):
        graph = Graph()

        # Find all entry points
        for function in self.lambda_functions:
            if function.get_parents() == []:  # No parent resourecs, so this is an entry point
                graph.add_entry_point(function)
            else:
                pass

        return graph