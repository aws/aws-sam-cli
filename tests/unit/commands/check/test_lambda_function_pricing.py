from unittest import TestCase
from unittest.mock import Mock, patch

from samcli.commands.check.resources.lambda_function_pricing import LambdaFunctionPricing


class TestLambdaFunctionPricing(TestCase):
    @patch("samcli.commands.check.resources.lambda_function_pricing.click")
    def test_ask_memory(self, patch_click):
        question_mock = "Mock()"

        lambda_pricing = LambdaFunctionPricing()
        patch_click.prompt.return_value = "5:GB"

        split_value = patch_click.prompt.return_value.split(":")

        lambda_pricing._validate_memory_input = Mock()
        lambda_pricing._validate_memory_input.return_value = True

        result0, result1 = lambda_pricing._ask_memory(question_mock)

        patch_click.prompt.assert_called_once_with(text=question_mock, type=str)
        lambda_pricing._validate_memory_input.assert_called_once_with(split_value)

        self.assertEqual(result0, split_value[0])
        self.assertEqual(result1, split_value[1])

    @patch("samcli.commands.check.resources.lambda_function_pricing.click")
    def test_validate_memory_input(self, patch_click):
        self_mock = Mock()
        self_mock._min_memory_amount = 128
        self_mock._max_memory_amount = 10000
        self_mock._max_num_requests = 1000000000000000000000
        self_mock._max_duration = 900000

        # All correct input
        memory_amount = "300"
        memory_unit = "MB"
        user_input_split = [memory_amount, memory_unit]

        result = LambdaFunctionPricing._validate_memory_input(self_mock, user_input_split)

        self.assertEqual(True, result)

        memory_amount = "2.58"
        memory_unit = "GB"
        user_input_split = [memory_amount, memory_unit]

        result = LambdaFunctionPricing._validate_memory_input(self_mock, user_input_split)

        self.assertEqual(True, result)

        # Incorrect user_input_split amount
        memory_amount = "600"
        memory_unit = "MB"
        user_input_split = [memory_amount, memory_unit, memory_unit]

        result = LambdaFunctionPricing._validate_memory_input(self_mock, user_input_split)

        self.assertEqual(False, result)

        # Invalid amount (not a number)
        memory_amount = "number"
        memory_unit = "MB"
        user_input_split = [memory_amount, memory_unit, memory_unit]

        result = LambdaFunctionPricing._validate_memory_input(self_mock, user_input_split)

        self.assertEqual(False, result)

        # Invalid unit
        memory_amount = "800"
        memory_unit = "TB"
        user_input_split = [memory_amount, memory_unit, memory_unit]

        result = LambdaFunctionPricing._validate_memory_input(self_mock, user_input_split)

        self.assertEqual(False, result)

        # Below range
        memory_amount = "80"
        memory_unit = "MB"
        user_input_split = [memory_amount, memory_unit, memory_unit]

        result = LambdaFunctionPricing._validate_memory_input(self_mock, user_input_split)

        self.assertEqual(False, result)

        # Above range
        memory_amount = "80"
        memory_unit = "GB"
        user_input_split = [memory_amount, memory_unit, memory_unit]

        result = LambdaFunctionPricing._validate_memory_input(self_mock, user_input_split)

        self.assertEqual(False, result)

    @patch("samcli.commands.check.resources.lambda_function_pricing.ask")
    @patch("samcli.commands.check.resources.lambda_function_pricing.LambdaFunctionPricing")
    def test_ask_questions(self, patch_LFPricing, patch_ask):
        pricing_instance_mock = Mock()
        patch_LFPricing.return_value = pricing_instance_mock

        pricing_instance_mock.set_number_of_requests = Mock()

        graph_mock = Mock()

        pricing = LambdaFunctionPricing()
        pricing._ask_memory = Mock()

        memory_mock = Mock()
        unit_mock = Mock()
        pricing._ask_memory.return_value = [memory_mock, unit_mock]

        patch_ask.return_value = Mock()

        pricing_instance_mock.number_of_requests = patch_ask.return_value
        pricing_instance_mock.average_duration = patch_ask.return_value
        pricing_instance_mock.allocated_memory = memory_mock
        pricing_instance_mock.allocated_memory_unit = unit_mock

        pricing.ask_questions()

        pricing._ask_memory.assert_called_once()
