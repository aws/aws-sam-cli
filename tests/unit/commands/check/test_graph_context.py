from unittest import TestCase
from unittest.mock import MagicMock, Mock, patch

from samcli.commands.check.graph_context import GraphContext, _check_input


class TestGraphContext(TestCase):
    @patch("samcli.commands.check.graph_context.CheckGraph")
    def test_generate(self, patch_graph):
        graph_mock = Mock()
        patch_graph.return_value = graph_mock

        graph_context = GraphContext(MagicMock())

        graph_context.make_connections = Mock()
        graph_context.find_entry_points = Mock()

        generated_graph = graph_context.generate()

        graph_context.make_connections.assert_called_once_with(graph_mock)
        graph_context.find_entry_points.assert_called_once_with(graph_mock)
        self.assertEqual(generated_graph, graph_mock)

    def test_handle_lambda_permissions(self):
        self_mock = Mock()

        permission_object = {}
        function_name_mock = Mock()
        function_object_mock = Mock()
        function_object_mock.parents = []
        source_name_mock = Mock()
        source_object_mock = Mock()
        source_object_mock.children = []

        permission_object = {
            "Properties": {
                "FunctionName": {"Ref": function_name_mock},
                "SourceArn": {"Fn::Sub": [None, {"__ApiId__": {"Ref": source_name_mock}}]},
            }
        }

        self_mock.lambda_functions = {function_name_mock: function_object_mock}
        self_mock.api_gateways = {source_name_mock: source_object_mock}

        permission_mock = Mock()
        permission_mock.resource_object = permission_object

        self_mock.lambda_permissions.values.return_value = [permission_mock]

        GraphContext.handle_lambda_permissions(self_mock)

        self.assertEqual(function_object_mock.parents[0], source_object_mock)
        self.assertEqual(source_object_mock.children[0], function_object_mock)

        self_mock.lambda_functions = {}

        with self.assertRaises(Exception):
            GraphContext.handle_lambda_permissions(self_mock)

    @patch("samcli.commands.check.graph_context.DynamoDB")
    def test_handle_event_source_mappings(self, patch_dynamo):
        self_mock = Mock()
        event_mock = Mock()
        function_name_mock = Mock()
        function_object_mock = Mock()
        function_object_mock = Mock()
        function_object_mock.parents = []
        source_object_mock = Mock()
        source_object_mock.children = []

        patch_dynamo.return_value = source_object_mock

        source_name = "arn:aws:dynamodb:region:id:path:num"

        event_object = {"Properties": {"FunctionName": {"Ref": function_name_mock}, "EventSourceArn": source_name}}

        event_mock.resource_object = event_object

        self_mock.event_source_mappings.values.return_value = [event_mock]
        self_mock.lambda_functions = {function_name_mock: function_object_mock}

        self_mock.dynamo_db_tables = {}

        GraphContext.handle_event_source_mappings(self_mock)

        self.assertEqual(function_object_mock.parents[0], source_object_mock)
        self.assertEqual(source_object_mock.children[0], function_object_mock)

    def test_find_entry_points(self):
        self_mock = Mock()
        graph_mock = Mock()
        graph_mock.entry_points = []

        function_object_mock = Mock()
        api_object_mock = Mock()
        dynamo_object_mock = Mock()

        function_object_mock.parents = []
        api_object_mock.parents = []
        dynamo_object_mock.parents = []

        self_mock.lambda_functions.values.return_value = [function_object_mock]
        self_mock.api_gateways.values.return_value = []
        self_mock.dynamo_db_tables.values.return_value = []

        GraphContext.find_entry_points(self_mock, graph_mock)

        self.assertEqual(graph_mock.entry_points[0], function_object_mock)

        self_mock.api_gateways.values.return_value = [api_object_mock]
        GraphContext.find_entry_points(self_mock, graph_mock)

        self.assertEqual(graph_mock.entry_points[-1], api_object_mock)

        self_mock.dynamo_db_tables.values.return_value = [dynamo_object_mock]
        GraphContext.find_entry_points(self_mock, graph_mock)

        self.assertEqual(graph_mock.entry_points[-1], dynamo_object_mock)

    def test_make_connections(self):
        self_mock = Mock()

        self_mock.handle_lambda_permissions = Mock()
        self_mock.handle_event_source_mappings = Mock()
        self_mock._handle_iam_roles = Mock()

        GraphContext.make_connections(self_mock, Mock())

        self_mock.handle_lambda_permissions.assert_called_once()
        self_mock.handle_event_source_mappings.assert_called_once()
        self_mock._handle_iam_roles.assert_called_once()

    def test_handle_iam_roles(self):
        lambda_function_name = ""
        lambda_function_mock = Mock()
        policy_mock = Mock()

        policies = [policy_mock]

        properties = {"ManagedPolicyArns": policies}

        self_mock = Mock()

        self_mock.lambda_functions = {lambda_function_name: lambda_function_mock}
        self_mock._get_properties.return_value = properties
        self_mock._dynamo_policies = policies
        self_mock._make_connection_from_policy = Mock()

        GraphContext._handle_iam_roles(self_mock)

        self_mock._get_properties.assert_called_once_with(lambda_function_mock)
        self_mock._make_connection_from_policy.assert_called_once_with("AWS::DynamoDB::Table", lambda_function_name)

    def test_get_properties(self):
        self_mock = Mock()

        properties_mock = Mock()

        iam_role_object = {"Properties": properties_mock}

        role_mock = Mock()
        role_mock.resource_object = iam_role_object

        lambda_function_role_name = Mock()
        lambda_function_resource_object = {"Properties": {"Role": {"Fn::GetAtt": [lambda_function_role_name]}}}

        self_mock._iam_roles = {lambda_function_role_name: role_mock}

        lambda_function_mock = Mock()
        lambda_function_mock.resource_object = lambda_function_resource_object

        result = GraphContext._get_properties(self_mock, lambda_function_mock)

        # Test return value
        self.assertEqual(result, properties_mock)

        # test error raised
        self_mock._iam_roles = {}

        with self.assertRaises(Exception):
            GraphContext._get_properties(self_mock, lambda_function_mock)

    def test_make_connection_from_policy(self):
        resource_mock = Mock()
        resource_mock.parents = []
        resources_selected = [resource_mock]

        child_resource_type = "AWS::DynamoDB::Table"
        lambda_function_name = Mock()
        lambda_function_mock = Mock()
        lambda_function_mock.children = []

        self_mock = Mock()
        self_mock._ask_dynamo_connection_question.return_value = resources_selected
        self_mock.lambda_functions = {lambda_function_name: lambda_function_mock}

        GraphContext._make_connection_from_policy(self_mock, child_resource_type, lambda_function_name)

        self.assertEqual(lambda_function_mock.children[0], resource_mock)
        self.assertEqual(resource_mock.parents[0], lambda_function_mock)

    @patch("samcli.commands.check.graph_context._check_input")
    @patch("samcli.commands.check.graph_context.click")
    def test_ask_dynamo_connection_question(self, patch_click, patch_check):
        lambda_function_name = ""
        dynamo_table_name = ""

        user_input_mock = Mock()
        selected_resource_mock = Mock()

        self_mock = Mock()
        self_mock.dynamo_db_tables = {dynamo_table_name: selected_resource_mock}

        choice = 1
        user_choices = [choice]

        patch_click.prompt.return_value = user_input_mock

        patch_check.return_value = True, user_choices

        result = GraphContext._ask_dynamo_connection_question(self_mock, lambda_function_name)

        patch_check.assert_called_once_with(user_input_mock, 1)
        patch_click.prompt.assert_called_once()

        self.assertEqual(result, [selected_resource_mock])

    @patch("samcli.commands.check.graph_context.click")
    def test_check_input(self, patch_click):
        # All valid input from user
        user_input = "1"
        max_item_number = 1

        bool_result, choices_result = _check_input(user_input, max_item_number)

        self.assertEqual(bool_result, True)
        self.assertEqual(choices_result, [1])

        # Non-int entered
        user_input = "One"
        max_item_number = 1

        bool_result, choices_result = _check_input(user_input, max_item_number)

        self.assertEqual(bool_result, False)
        self.assertEqual(choices_result, [])

        # Outside of range
        user_input = "1:2:3:4"
        max_item_number = 3

        bool_result, choices_result = _check_input(user_input, max_item_number)

        self.assertEqual(bool_result, False)
        self.assertEqual(choices_result, [])
