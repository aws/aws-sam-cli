"""
Tests for print_result.py
"""
from unittest import TestCase
from unittest.mock import Mock, patch
from samcli.commands.check.results import Results


class TestPrintResults(TestCase):
    @patch("samcli.commands.check.results._print_warnings")
    @patch("samcli.commands.check.results.click")
    def test_print_bottle_neck_results(self, patch_click, patch_print):
        graph_mock = Mock()
        graph_mock.green_warnings = Mock()
        graph_mock.yellow_warnings = Mock()
        graph_mock.red_warnings = Mock()
        graph_mock.red_burst_warnings = Mock()

        patch_click.secho = Mock()

        print_results = Results(graph_mock, Mock())

        print_results.print_bottle_neck_results()

        patch_print.assert_any_call(graph_mock.green_warnings)
        patch_print.assert_any_call(graph_mock.yellow_warnings)
        patch_print.assert_any_call(graph_mock.red_warnings)
        patch_print.assert_any_call(graph_mock.red_burst_warnings)
