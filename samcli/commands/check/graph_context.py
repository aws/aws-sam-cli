from .resources.Graph import Graph


class GraphContext:
    def __init__(self, lambda_functions, resources):
        self.lambda_functions = lambda_functions
        self.resources = resources

    def generate(self):
        graph = Graph()

        self.make_connections(graph)
        self.find_entry_points(graph)

        return graph

    def make_connections(self, graph):
        lambda_permissions = self.resources["LambdaPermissions"]
        api_gateways = self.resources["ApiGateways"]

        print(lambda_permissions)
        print(api_gateways)

    def find_entry_points(self, graph):
        for function_name in self.lambda_functions:
            function_object = self.lambda_functions[function_name]
            if function_object.get_parents() == []:  # No parent resourecs, so this is an entry point
                graph.add_entry_point(function_object)
            else:
                pass
