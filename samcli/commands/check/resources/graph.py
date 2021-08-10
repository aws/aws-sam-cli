"""
Class for graph. All data is stored in the graph directly, or within nodes that are stored in the graph
"""
from typing import Dict, List, Tuple, Union, OrderedDict

import click

from samcli.commands.check.resources.lambda_function import LambdaFunction
from samcli.commands.check.resources.lambda_function_permission import LambdaFunctionPermission
from samcli.commands.check.resources.api_gateway import ApiGateway
from samcli.commands.check.resources.dynamo_db import DynamoDB
from samcli.commands.check.resources.event_source_mapping import EventSourceMapping
from samcli.commands.check.resources.i_am_role import IAMRole
from samcli.commands.check.resources.warning import CheckWarning
from samcli.commands.check.resources.unique_pricing_info import UniquePricingInfo


class CheckGraph:
    """
    A graph object stores four main item types.

    entry_points: All possible entry points to the application based on the template.
    resources_to_analyze: All resources that need to be directly checked for bottle
      neck issues (just lambda functions for now).
    green/yellow/red/red_burst_warnings: The four different warning types that
      the user can be presented
    unique_pricing_info: Contains the user entered data for all pricing questions
      for every resource
    """

    entry_points: List[Union[LambdaFunction]]
    resources_to_analyze: List[Union[LambdaFunction]]
    green_warnings: List[CheckWarning]
    yellow_warnings: List[CheckWarning]
    red_warnings: List[CheckWarning]
    red_burst_warnings: List[CheckWarning]
    unique_pricing_info: Dict[str, UniquePricingInfo]

    _lambda_permissions: List[LambdaFunctionPermission]
    _api_gateways: List[ApiGateway]
    _lambda_functions: List[LambdaFunction]
    _event_source_mappings: List[EventSourceMapping]
    _dynamo_db_tables: List[DynamoDB]
    _iam_roles: List[IAMRole]
    _dynamo_policies: Dict

    def __init__(self, resources):
        self.entry_points = []
        self.resources_to_analyze = {}
        self.green_warnings = []
        self.yellow_warnings = []
        self.red_warnings = []
        self.red_burst_warnings = []
        self.unique_pricing_info = {}

        if resources:
            # these are needed for graph generation, which does not happen when
            # data is loaded from the samconfig.toml file
            self._lambda_permissions = resources["LambdaPermissions"]
            self._api_gateways = resources["ApiGateways"]
            self._lambda_functions = resources["LambdaFunctions"]
            self._event_source_mappings = resources["EventSourceMappings"]
            self._dynamo_db_tables = resources["DynamoDBTables"]
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

    def generate(self) -> None:
        """
        Generates the graph based on the connections calulated
        """
        self._make_connections()
        self._find_entry_points()

    def _handle_lambda_permissions(self) -> None:
        """
        Certain resoures, such as ApiGateways, linked resources in a permission prod. Any other
        resources that do so will be handled here
        """
        for permission in self._lambda_permissions.values():
            permission_object = permission.resource_object

            ref_function_name = permission_object["Properties"]["FunctionName"]["Ref"]
            source_name = permission_object["Properties"]["SourceArn"]["Fn::Sub"][1]["__ApiId__"]["Ref"]

            if ref_function_name in self._lambda_functions and source_name in self._api_gateways:
                ref_object = self._lambda_functions[ref_function_name]
                source_object = self._api_gateways[source_name]

                source_object.children.append(ref_object)
                ref_object.parents.append(source_object)

            else:
                raise Exception(
                    "Graph generation error. Failed to find reference function and source for a permission prod"
                )

    def _handle_event_source_mappings(self) -> None:
        """
        DynamoDB tables, Kinesis streams, SQS queues, and MSK link themselves to lambda functions through
        EventSourceMapping objects. Those are handled here.
        """
        for event in self._event_source_mappings.values():
            event_object = event.resource_object

            ref_function_name = event_object["Properties"]["FunctionName"]["Ref"]
            ref_function_object = self._lambda_functions[ref_function_name]

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
                    self._dynamo_db_tables[source_name] = source_object

                    source_object.children.append(ref_function_object)
                    ref_function_object.parents.append(source_object)
            else:
                # This resource does exist in the template. No extra steps are needed
                source_name = source_name.split(".")[0]

                # Check all tables, as the event does not contain the type of resource in "EventSourceArn"
                if source_name in self._dynamo_db_tables:
                    source_object = self._dynamo_db_tables[source_name]

                    source_object.children.append(ref_function_object)
                    ref_function_object.parents.append(source_object)

    def _find_entry_points(self) -> None:
        """
        Finds all entry point resources from each resource type
        """
        for function_object in self._lambda_functions.values():
            if function_object.parents == []:  # No parent resourecs, so this is an entry point
                self.entry_points.append(function_object)

        for api_object in self._api_gateways.values():
            if api_object.parents == []:
                self.entry_points.append(api_object)

        for dynamo_object in self._dynamo_db_tables.values():
            if dynamo_object.parents == []:
                self.entry_points.append(dynamo_object)

    def _make_connections(self) -> None:
        """
        Makes connections between resources based on how those connections are
        defined in a CFN template.
        """
        # Start with lambda function permissions, if there are any
        self._handle_lambda_permissions()

        # Next do all event source mappings, if any exist
        self._handle_event_source_mappings()

        # Finally, handle all policies defined for lambda functions
        self._handle_iam_roles()

    def _handle_iam_roles(self) -> None:
        """
        Checks IAM_Roles to see what connections between resources need to be made
        """
        for lambda_function_name, lambda_function in self._lambda_functions.items():

            properties = self._get_properties(lambda_function)

            # there may not be policies.
            if "ManagedPolicyArns" in properties:
                policies = properties["ManagedPolicyArns"]

                for policy in policies:
                    """
                    Only the policy name is given. What resource the policy is for is not known. "
                    All policies must be checked. Policies can also include what has access to
                    the lambda function. Those are ignored, as they are handled elsewhere
                    """

                    if policy in self._dynamo_policies:
                        self._make_connection_from_policy("AWS::DynamoDB::Table", lambda_function_name)

    def _get_properties(self, lambda_function: LambdaFunction) -> OrderedDict:
        """
        Gets properties of lambda functions, hich are defined in a CFN template
        """
        lambda_function_resource_object = lambda_function.resource_object

        lambda_function_role_name = lambda_function_resource_object["Properties"]["Role"]["Fn::GetAtt"][0]

        if lambda_function_role_name not in self._iam_roles:
            raise Exception("Failed to find IAM Role")

        iam_role = self._iam_roles[lambda_function_role_name]

        iam_role_object = iam_role.resource_object

        return iam_role_object["Properties"]

    def _make_connection_from_policy(self, child_resource_type: str, lambda_function_name: str) -> None:
        """
        The child_resource_type represents what type of resource the child is.
        There may be multiple resources appended to "resources_selected", but they will all be of the same type per
        _make_connection_from_policy" instance

        Parameters
        ----------
            child_resource_type: str
                The resource type for the child resource of the current resource
            lambda_function_name: str
                The name of the current lambda function
        """
        if child_resource_type == "AWS::DynamoDB::Table":
            resources_selected = self._ask_dynamo_connection_question(lambda_function_name)

            lambda_function = self._lambda_functions[lambda_function_name]

            for resource in resources_selected:
                lambda_function.children.append(resource)
                resource.parents.append(lambda_function)

    def _ask_dynamo_connection_question(self, lambda_function_name: str) -> List[DynamoDB]:
        """
        Lambda functions can have access to dynamoDB tables, but the template does not specify what table(s)
        it has access to. The user must specift what table(s) the lambda function has permission to access

        Parameters
        ----------
            lambda_function_name: str
                The name of the current lambda function

        Returns
        -------
            List[DynamoDB]:
                Returns the list of dynamoDb tab;es the user selected.
        """
        resources_selected = []
        valid_user_input = False

        info_prompt = "The Lambda Function [%s] has access to DynamoDB. Here are all the tables that we found:\n" % (
            lambda_function_name
        )

        displayed_resources_names = []

        for item_number, dynamo_table_name in enumerate(self._dynamo_db_tables):
            info_prompt += "[%i] %s\n" % (item_number + 1, dynamo_table_name)
            displayed_resources_names.append(dynamo_table_name)

        user_input = ""
        user_choices = []

        while not valid_user_input:

            click.echo(info_prompt)
            user_input = click.prompt(
                "Which table(s) does the function write to? To select multiple tables, separate each selection "
                'with a ":"',
                type=str,
            )

            valid_user_input, user_choices = _check_input(user_input, item_number + 1)

        for choice in user_choices:
            choice -= 1  # list display starts at 1. choice -= 1 to account for this
            resource_choice = displayed_resources_names[choice]

            selected_resource = self._dynamo_db_tables[resource_choice]
            resources_selected.append(selected_resource)

        return resources_selected


def _check_input(user_input: str, max_item_number: int) -> Tuple[bool, List[int]]:
    """
    Checks the user input to ensure it's within the specified range

    Paramters
    ---------
        user_input: str
            The users input
        max_item_number: int
            The amximum mount of items to select from

    Returns
    -------
        Tuple[bool, List[int]]:
            Returns a bool on whether the inpout is valid or not. Returns a list of
            the user selcted choices.
    """
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
