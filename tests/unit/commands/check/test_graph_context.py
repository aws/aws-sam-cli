from unittest import TestCase
from unittest.mock import Mock, patch

from samcli.commands.check.graph_context import GraphContext


class TestGraphContext(TestCase):
    @patch("samcli.commands.check.graph_context.Graph")
    def test_class(self, patched_graph):
        lambda_mock = Mock()
        lambda_mock.parents = []
        lambda_functions = [lambda_mock]

        graph_context_mock = Mock()

        patched_graph.return_value = graph_context_mock
        graph_context_mock.entry_points.append = Mock()

        graph_context = GraphContext(lambda_functions)
        graph_context.generate()

        graph_context_mock.entry_points.append.assert_called_once_with(lambda_mock)
