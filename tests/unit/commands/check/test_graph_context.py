from unittest import TestCase
from unittest.mock import MagicMock, Mock, patch

from samcli.commands.check.graph_context import GraphContext


class TestGraphContext(TestCase):
    @patch("samcli.commands.check.graph_context.Graph")
    def test_generate(self, patch_graph):
        graph_mock = Mock()
        patch_graph.return_value = graph_mock

        graph_context = GraphContext(MagicMock())

        graph_context.make_connections = Mock()
        graph_context.find_entry_points = Mock()

        graph_context.make_connections.return_value = Mock()
        graph_context.find_entry_points.return_value = Mock()

        generated_graph = graph_context.generate()

        graph_context.make_connections.assert_called_once_with(graph_mock)
        graph_context.find_entry_points.assert_called_once_with(graph_mock)
        self.assertEqual(generated_graph, graph_mock)

    def test_handle_lambda_permissions(self):
        self_mock = Mock()

        permission_object = {}
        function_name_mock = Mock()
        function_object_mock = Mock()
        source_name_mock = Mock()
        source_object_mock = Mock()

        permission_object = {
            "Properties": {
                "FunctionName": {"Ref": function_name_mock},
                "SourceArn": {"Fn::Sub": [None, {"__ApiId__": {"Ref": source_name_mock}}]},
            }
        }

        self_mock.lambda_functions = {function_name_mock: function_object_mock}
        self_mock.api_gateways = {source_name_mock: source_object_mock}

        permission_mock = Mock()
        permission_mock.get_resource_object.return_value = permission_object

        self_mock.lambda_permissions.values.return_value = [permission_mock]

        source_object_mock.add_child = Mock()
        function_object_mock.add_parent = Mock()

        GraphContext.handle_lambda_permissions(self_mock)

        source_object_mock.add_child.assert_called_once_with(function_object_mock)
        function_object_mock.add_parent.assert_called_once_with(source_object_mock)

        self_mock.lambda_permissions.values.return_value = []
        GraphContext.handle_lambda_permissions(self_mock)

        self.assertRaises(Exception)

    @patch("samcli.commands.check.graph_context.DynamoDB")
    def test_handle_event_source_mappings(self, patch_dynamo):
        self_mock = Mock()
        event_mock = Mock()
        function_name_mock = Mock()
        function_object_mock = Mock()
        source_object_mock = Mock()

        patch_dynamo.return_value = source_object_mock

        source_name = "arn:aws:dynamodb:region:id:path:num"

        event_object = {"Properties": {"FunctionName": {"Ref": function_name_mock}, "EventSourceArn": source_name}}

        event_mock.get_resource_object.return_value = event_object

        self_mock.event_source_mappings.values.return_value = [event_mock]
        self_mock.lambda_functions = {function_name_mock: function_object_mock}

        self_mock.dynamoDB_tables = {}

        source_object_mock.add_child = Mock()
        function_object_mock.add_parent = Mock()

        GraphContext.handle_event_source_mappings(self_mock)

        source_object_mock.add_child.assert_called_once_with(function_object_mock)
        function_object_mock.add_parent.assert_called_once_with(source_object_mock)

    def test_make_connections(self):
        self_mock = Mock()

        self_mock.handle_lambda_permissions = Mock()
        self_mock.handle_event_source_mappings = Mock()

        GraphContext.make_connections(self_mock, Mock())

        self_mock.handle_lambda_permissions.assert_called_once()
        self_mock.handle_event_source_mappings.assert_called_once()

    def test_find_entry_points(self):
        self_mock = Mock()
        graph_mock = Mock()

        graph_mock.add_entry_point = Mock()

        function_object_mock = Mock()
        api_object_mock = Mock()
        dynamo_object_mock = Mock()

        function_object_mock.get_parents.return_value = []
        api_object_mock.get_parents.return_value = []
        dynamo_object_mock.get_parents.return_value = []

        self_mock.lambda_functions.values.return_value = [function_object_mock]
        self_mock.api_gateways.values.return_value = []
        self_mock.dynamoDB_tables.values.return_value = []

        GraphContext.find_entry_points(self_mock, graph_mock)
        graph_mock.add_entry_point.assert_called_with(function_object_mock)

        self_mock.api_gateways.values.return_value = [api_object_mock]
        GraphContext.find_entry_points(self_mock, graph_mock)
        graph_mock.add_entry_point.assert_called_with(api_object_mock)

        self_mock.dynamoDB_tables.values.return_value = [dynamo_object_mock]
        GraphContext.find_entry_points(self_mock, graph_mock)
        graph_mock.add_entry_point.assert_called_with(dynamo_object_mock)
