from unittest import TestCase
from unittest.mock import Mock, patch

from samcli.commands.check.resources.graph import CheckGraph


class TestGraph(TestCase):
    def test_class(self):
        entry_point_mock = Mock()
        resource_mock = Mock()

        lambda_functions = []

        key = "key"

        graph = CheckGraph(lambda_functions)

        graph.entry_points.append(entry_point_mock)
        graph.resources_to_analyze[key] = resource_mock

        self.assertEqual(entry_point_mock, graph.entry_points[0])
        self.assertEqual(resource_mock, graph.resources_to_analyze[key])
