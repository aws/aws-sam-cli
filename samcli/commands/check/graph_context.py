from typing import List, OrderedDict
import click

from samcli.commands.check.resources.dynamo_db import DynamoDB
from samcli.commands.check.resources.lambda_function import LambdaFunction
from samcli.commands.check.resources.graph import CheckGraph


class GraphContext:
    def __init__(self, resources):
        self.lambda_permissions = resources["LambdaPermissions"]
        self.api_gateways = resources["ApiGateways"]
        self.lambda_functions = resources["LambdaFunctions"]
        self.event_source_mappings = resources["EventSourceMappings"]
        self.dynamoDB_tables = resources["DynamoDBTables"]
        self._iam_roles = resources["IAMRoles"]
        self._dynamo_policies = {
            "DynamoDBCrudPolicy": True,
            "DynamoDBReadPolicy": True,
            "DynamoDBWritePolicy": True,
            "DynamoDBReconfigurePolicy": True,
            "DynamoDBStreamReadPolicy": True,
            "DynamoDBBackupFullAccessPolicy": True,
            "DynamoDBRestoreFromBackupPolicy": True,
        }

    def generate(self):
        graph = CheckGraph([])

        self.make_connections(graph)
        self.find_entry_points(graph)

        return graph

    def handle_lambda_permissions(self):
        for permission in self.lambda_permissions.values():
            """
            Certain resoures, such as ApiGateways, linked resources in a permission prod. Any other
            resources that do so will be handled here
            """
            permission_object = permission.resource_object

            ref_function_name = permission_object["Properties"]["FunctionName"]["Ref"]
            source_name = permission_object["Properties"]["SourceArn"]["Fn::Sub"][1]["__ApiId__"]["Ref"]

            if ref_function_name in self.lambda_functions and source_name in self.api_gateways:
                ref_object = self.lambda_functions[ref_function_name]
                source_object = self.api_gateways[source_name]

                source_object.children.append(ref_object)
                ref_object.parents.append(source_object)

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
            event_object = event.resource_object

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

                    source_object.children.append(ref_function_object)
                    ref_function_object.parents.append(source_object)
            else:
                # This resource does exist in the template. No extra steps are needed
                source_name = source_name.split(".")[0]

                # Check all tables, as the event does not contain the type of resource in "EventSourceArn"
                if source_name in self.dynamoDB_tables:
                    source_object = self.dynamoDB_tables[source_name]

                    source_object.children.append(ref_function_object)
                    ref_function_object.parents.append(source_object)

    def find_entry_points(self, graph):
        for function_object in self.lambda_functions.values():
            if function_object.parents == []:  # No parent resourecs, so this is an entry point
                graph.entry_points.append(function_object)

        for api_object in self.api_gateways.values():
            if api_object.parents == []:
                graph.entry_points.append(api_object)

        for dynamo_object in self.dynamoDB_tables.values():
            if dynamo_object.parents == []:
                graph.entry_points.append(dynamo_object)

    def make_connections(self, graph):
        # Start with lambda function permissions, if there are any
        self.handle_lambda_permissions()

        # Next do all event source mappings, if any exist
        self.handle_event_source_mappings()

        # Finally, handle all policies defined for lambda functions
        self._handle_iam_roles()

    def _handle_iam_roles(self):
        for lambda_function_name, lambda_function in self.lambda_functions.items():

            properties = self._get_properties(lambda_function)

            # there may not be policies.
            if "ManagedPolicyArns" in properties:
                policies = properties["ManagedPolicyArns"]

                for policy in policies:
                    """
                    Only the policy name is given. What resource the policy is for is not known. All policies must be checked.
                    Policies can also include what has access to the lambda function. Those are ignored, as they are handled elsewhere
                    """

                    if policy in self._dynamo_policies:
                        self._make_connection_from_policy("AWS::DynamoDB::Table", lambda_function_name)

    def _get_properties(self, lambda_function: LambdaFunction) -> OrderedDict:
        lambda_function_resource_object = lambda_function.resource_object

        lambda_function_role_name = lambda_function_resource_object["Properties"]["Role"]["Fn::GetAtt"][0]

        if lambda_function_role_name not in self._iam_roles:
            raise Exception("Failed to find IAM Role")

        iam_role = self._iam_roles[lambda_function_role_name]

        iam_role_object = iam_role.resource_object

        return iam_role_object["Properties"]

    def _make_connection_from_policy(self, child_resource_type: str, lambda_function_name: str):
        """
        The child_resource_type represents what type of resource the child is.
        There may be multiple resources appended to "resources_selected", but they will all be of the same type per
        "_make_connection_from_policy" instance
        """
        if child_resource_type == "AWS::DynamoDB::Table":
            resources_selected = self._ask_dynamo_connection_question(lambda_function_name)

            lambda_function = self.lambda_functions[lambda_function_name]

            for resource in resources_selected:
                lambda_function.children.append(resource)
                resource.parents.append(lambda_function)

    def _ask_dynamo_connection_question(self, lambda_function_name: str) -> List:
        resources_selected = []
        valid_user_input = False

        info_prompt = "The Lambda Function [%s] has access to DynamoDB. Here are all the tables that we found:\n" % (
            lambda_function_name
        )

        displayed_resources_names = []

        for item_number, dynamo_table_name in enumerate(self.dynamoDB_tables):
            info_prompt += "[%i] %s\n" % (item_number + 1, dynamo_table_name)
            displayed_resources_names.append(dynamo_table_name)

        user_input = ""
        user_choices = []

        while not valid_user_input:

            click.echo(info_prompt)
            user_input = click.prompt(
                'Which table(s) does the function write to? To select multiple tables, separate each selection with a ":"',
                type=str,
            )

            valid_user_input, user_choices = _check_input(user_input, item_number + 1)

        for choice in user_choices:
            choice -= 1  # list display starts at 1. choice -= 1 to account for this
            resource_choice = displayed_resources_names[choice]

            selected_resource = self.dynamoDB_tables[resource_choice]
            resources_selected.append(selected_resource)

        return resources_selected


def _check_input(user_input: str, max_item_number: int) -> bool:
    user_choices = user_input.split(":")

    for selection in user_choices:
        try:  # check if the user enteredd a valid int
            value = int(selection)
        except ValueError:
            click.echo("Incorrect value entered. Please enter a valid input")
            return False, []

        if value <= 0 or value > max_item_number:
            click.echo("Numbers out of range. Please select values within the list range.")
            return False, []

    user_choices_ints = []
    for choice in user_choices:  # convert each choice to an int
        user_choices_ints.append(int(choice))

    return True, user_choices_ints
