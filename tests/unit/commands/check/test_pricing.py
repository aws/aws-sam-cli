from samcli.commands.check.resources.LambdaFunctionPricing import LambdaFunctionPricing
from unittest import TestCase
from unittest.mock import Mock, patch

from samcli.commands.check.resources.Pricing import Pricing


class TestPricing(TestCase):
    @patch("samcli.commands.check.resources.Pricing.click")
    def test_ask(self, patch_click):
        graph_mock = Mock()
        question_mock = "Mock()"

        pricing = Pricing(graph_mock)
        patch_click.prompt.return_value = 5

        result = pricing.ask(question_mock, 1, 10)

        patch_click.prompt.assert_called_once_with(text=question_mock, type=int)
        self.assertEqual(result, patch_click.prompt.return_value)

    @patch("samcli.commands.check.resources.Pricing.click")
    def test_ask_memory(self, patch_click):
        graph_mock = Mock()
        question_mock = "Mock()"

        pricing = Pricing(graph_mock)
        patch_click.prompt.return_value = "5:GB"

        split_value = patch_click.prompt.return_value.split(":")

        pricing.correct_memory_input = Mock()
        pricing.correct_memory_input.return_value = True

        result0, result1 = pricing.ask_memory(question_mock, 1, 10)

        patch_click.prompt.assert_called_once_with(text=question_mock, type=str)
        pricing.correct_memory_input.assert_called_once_with(split_value)

        self.assertEqual(result0, split_value[0])
        self.assertEqual(result1, split_value[1])

    @patch("samcli.commands.check.resources.Pricing.click")
    def test_correct_memory_input(self, patch_click):
        # All correct input
        memory_amount = "300"
        memory_unit = "MB"
        user_input_split = [memory_amount, memory_unit]

        result = Pricing.correct_memory_input(Mock(), user_input_split)

        self.assertEqual(True, result)

        memory_amount = "2.58"
        memory_unit = "GB"
        user_input_split = [memory_amount, memory_unit]

        result = Pricing.correct_memory_input(Mock(), user_input_split)

        self.assertEqual(True, result)

        # Incorrect user_input_split amount
        memory_amount = "600"
        memory_unit = "MB"
        user_input_split = [memory_amount, memory_unit, memory_unit]

        result = Pricing.correct_memory_input(Mock(), user_input_split)

        self.assertEqual(False, result)

        # Invalid amount (not a number)
        memory_amount = "number"
        memory_unit = "MB"
        user_input_split = [memory_amount, memory_unit, memory_unit]

        result = Pricing.correct_memory_input(Mock(), user_input_split)

        self.assertEqual(False, result)

        # Invalid unit
        memory_amount = "800"
        memory_unit = "TB"
        user_input_split = [memory_amount, memory_unit, memory_unit]

        result = Pricing.correct_memory_input(Mock(), user_input_split)

        self.assertEqual(False, result)

        # Below range
        memory_amount = "80"
        memory_unit = "MB"
        user_input_split = [memory_amount, memory_unit, memory_unit]

        result = Pricing.correct_memory_input(Mock(), user_input_split)

        self.assertEqual(False, result)

        # Above range
        memory_amount = "80"
        memory_unit = "GB"
        user_input_split = [memory_amount, memory_unit, memory_unit]

        result = Pricing.correct_memory_input(Mock(), user_input_split)

        self.assertEqual(False, result)

    def test_ask_pricing_questions(self):
        self_mock = Mock()
        resource_mock = Mock()
        resource_mock.get_resource_type.return_value = "AWS::Lambda::Function"
        self_mock.graph.get_resources_to_analyze.return_value = [resource_mock]

        result = Pricing.ask_pricing_questions(self_mock)

        self_mock.ask_lambda_function_questions.assert_called_with(resource_mock)

    @patch("samcli.commands.check.resources.Pricing.LambdaFunctionPricing")
    def test_ask_lambda_function_questions(self, patch_LFPricing):
        pricing_instance_mock = Mock()
        patch_LFPricing.return_value = pricing_instance_mock

        pricing_instance_mock.set_number_of_requests = Mock()

        graph_mock = Mock()
        lambda_function_mock = Mock()

        pricing = Pricing(graph_mock)
        pricing.ask = Mock()
        pricing.ask_memory = Mock()

        memory_mock = Mock()
        unit_mock = Mock()
        pricing.ask_memory.return_value = [memory_mock, unit_mock]

        pricing.ask_lambda_function_questions(lambda_function_mock)

        pricing_instance_mock.set_number_of_requests.assert_called_once_with(pricing.ask.return_value)
        pricing_instance_mock.set_average_duration.assert_called_once_with(pricing.ask.return_value)
        pricing_instance_mock.set_allocated_memory.assert_called_once_with(memory_mock)
        pricing_instance_mock.set_allocated_memory_unit.assert_called_once_with(unit_mock)
        lambda_function_mock.set_pricing_info.assert_called_once_with(pricing_instance_mock)
