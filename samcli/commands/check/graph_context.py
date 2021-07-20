from .resources.Graph import Graph
from samcli.commands.check.resources.DynamoDB import DynamoDB


class GraphContext:
    def __init__(self, resources):
        self.lambda_permissions = resources["LambdaPermissions"]
        self.api_gateways = resources["ApiGateways"]
        self.lambda_functions = resources["LambdaFunctions"]
        self.event_source_mappings = resources["EventSourceMappings"]
        self.dynamoDB_tables = resources["DynamoDBTables"]

    def generate(self):
        graph = Graph()

        self.make_connections(graph)
        self.find_entry_points(graph)

        return graph

    def handle_lambda_permissions(self):
        for permission in self.lambda_permissions.values():
            """
            Certain resoures, such as ApiGateways, linked resources in a permission prod. Any other
            resources that do so will be handled here
            """
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

    def handle_event_source_mappings(self):
        for event in self.event_source_mappings.values():
            """
            DynamoDB tables, Kinesis streams, SQS queues, and MSK link themselves to lambda functions through
            EventSourceMapping objects. Those are handled here.
            """
            event_object = event.get_resource_object()

            ref_function_name = event_object["Properties"]["FunctionName"]["Ref"]
            ref_function_object = self.lambda_functions[ref_function_name]

            source_name = event_object["Properties"]["EventSourceArn"]

            source_name_split = source_name.split(":")

            if source_name_split[0] == "arn":
                """
                This resource is not defined in the template, but exists somewhere outside of it already deployed.
                When this happens, a new object of appropriate type needs to be generated and added to the graph.
                Currently, the graph does not contain this object/resource, because it was never defined in the
                template (this is allowed). Generate the new resource, add it to the graph, then make the
                appropriate connections.
                """
                source_type = source_name_split[2]

                if source_type == "dynamodb":
                    source_name = source_name_split[5]
                    # Until the resource_object is needed, just use an empty {} for now
                    source_object = DynamoDB({}, "AWS::DynamoDB::Table", source_name)
                    self.dynamoDB_tables[source_name] = source_object

                    source_object.add_child(ref_function_object)
                    ref_function_object.add_parent(source_object)
            else:
                # This resource does exist in the template. No extra steps are needed
                source_name = source_name.split(".")[0]

                # Check all tables, as the event does not contain the type of resource in "EventSourceArn"
                if source_name in self.dynamoDB_tables:
                    source_object = self.dynamoDB_tables[source_name]

                    source_object.add_child(ref_function_object)
                    ref_function_object.add_parent(source_object)

    def make_connections(self, graph):

        # Start with lambda function permissions, if there are any
        self.handle_lambda_permissions()

        # Next do all event source mappings, if any exist
        self.handle_event_source_mappings()

    def find_entry_points(self, graph):
        for function_object in self.lambda_functions.values():
            if function_object.get_parents() == []:  # No parent resourecs, so this is an entry point
                graph.add_entry_point(function_object)

        for api_object in self.api_gateways.values():
            if api_object.get_parents() == []:
                graph.add_entry_point(api_object)

        for dynamo_object in self.dynamoDB_tables.values():
            if dynamo_object.get_parents() == []:
                graph.add_entry_point(dynamo_object)
