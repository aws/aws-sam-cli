from unittest import TestCase
from unittest.mock import Mock, patch

from samcli.commands.check.resources.pricing import CheckPricing
from samcli.commands._utils.resources import AWS_LAMBDA_FUNCTION


class TestPricing(TestCase):
    @patch("samcli.commands.check.resources.pricing.LambdaFunctionPricing")
    def test_ask_pricing_questions(self, patch_lambda_pricing):
        self_mock = Mock()
        self_mock._asked_lambda_questions = False

        resource_mock = Mock()
        resource_mock.resource_type = AWS_LAMBDA_FUNCTION
        self_mock._graph.resources_to_analyze.values.return_value = [resource_mock]
        self_mock._graph.unique_pricing_info = {}

        lambda_pricing_mock = Mock()
        lambda_pricing_mock.ask_questions = Mock()

        patch_lambda_pricing.return_value = lambda_pricing_mock

        CheckPricing.ask_pricing_questions(self_mock)

        lambda_pricing_mock.ask_questions.assert_called_once()

        self.assertEqual(self_mock._graph.unique_pricing_info["LambdaFunction"], lambda_pricing_mock)
