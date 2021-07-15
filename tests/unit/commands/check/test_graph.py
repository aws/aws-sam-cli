from unittest import TestCase
from unittest.mock import Mock, patch

from samcli.commands.check.resources.Graph import Graph


class TestGraph(TestCase):
    def test_class(self):
        entry_point_mock = Mock()
        resource_mock = Mock()

        graph = Graph()

        graph.add_entry_point(entry_point_mock)
        graph.add_resource_to_analyze(resource_mock)

        self.assertEqual(entry_point_mock, graph.get_entry_points()[0])
        self.assertEqual(resource_mock, graph.get_resources_to_analyze()[0])
