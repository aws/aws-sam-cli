from .resources.Graph import Graph


class GraphContext:
    def __init__(self, resources):
        self.lambda_permissions = resources["LambdaPermissions"]
        self.api_gateways = resources["ApiGateways"]
        self.lambda_functions = resources["LambdaFunctions"]

    def generate(self):
        graph = Graph()

        self.make_connections(graph)
        self.find_entry_points(graph)

        return graph

    def make_connections(self, graph):

        # Start with lambda function permissions, if there are any
        for permission in self.lambda_permissions.values():
            permission_object = permission.get_resource_object()

            ref_function_name = permission_object["Properties"]["FunctionName"]["Ref"]
            source_name = permission_object["Properties"]["SourceArn"]["Fn::Sub"][1]["__ApiId__"]["Ref"]

            if ref_function_name in self.lambda_functions and source_name in self.api_gateways:
                ref_object = self.lambda_functions[ref_function_name]
                source_object = self.api_gateways[source_name]

                source_object.add_child(ref_object)
                ref_object.add_parent(source_object)

            else:
                raise Exception(
                    "Graph generation error. Failed to find reference function and source for a permission prod"
                )

    def find_entry_points(self, graph):
        for function_object in self.lambda_functions.values():
            if function_object.get_parents() == []:  # No parent resourecs, so this is an entry point
                graph.add_entry_point(function_object)

        for api_object in self.api_gateways.values():
            if api_object.get_parents() == []:
                graph.add_entry_point(api_object)
