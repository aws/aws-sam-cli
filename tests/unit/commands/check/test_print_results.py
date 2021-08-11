"""
Tests for print_result.py
"""
from unittest import TestCase
from unittest.mock import Mock, patch
from samcli.commands.check.print_results import CheckResults


class TestPrintResults(TestCase):
    @patch("samcli.commands.check.print_results._print_warnings")
    @patch("samcli.commands.check.print_results.click")
    def test_print_bottle_neck_results(self, patch_click, patch_print):
        graph_mock = Mock()
        graph_mock.green_warnings = Mock()
        graph_mock.yellow_warnings = Mock()
        graph_mock.red_warnings = Mock()
        graph_mock.red_burst_warnings = Mock()

        lambda_pricing_results = 0.0

        patch_click.secho = Mock()

        print_results = CheckResults(graph_mock, lambda_pricing_results)

        print_results.print_bottle_neck_results()

        patch_print.assert_any_call(graph_mock.green_warnings)
        patch_print.assert_any_call(graph_mock.yellow_warnings)
        patch_print.assert_any_call(graph_mock.red_warnings)
        patch_print.assert_any_call(graph_mock.red_burst_warnings)
