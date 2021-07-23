from unittest import TestCase
from unittest.mock import Mock, patch

from samcli.commands.check.bottle_necks import BottleNecks, ask


class TestBottleNeck(TestCase):
    @patch("samcli.commands.check.bottle_necks.click")
    def test_ask(self, click_patch):
        click_patch.prompt.return_value = 5
        question = "question"
        result = ask(question, 1, 10)

        self.assertEqual(result, click_patch.prompt.return_value)
        click_patch.prompt.assert_called_with(text=question, type=int)

    @patch("samcli.commands.check.bottle_necks.ask")
    @patch("samcli.commands.check.bottle_necks.click")
    def test_ask_entry_point_question(self, click_patch, patch_ask):
        graph_mock = Mock()
        entry_point_mock = Mock()
        entry_points = [entry_point_mock]

        entry_point_mock.get_name.return_value = Mock()

        question = "We found the following resources in your application that could be the entry point for a request."

        question += "\n[%i] %s" % (1, entry_point_mock.get_name.return_value) + "\nWhere should the simulation start?"

        graph_mock.get_entry_points.return_value = entry_points

        bottle_neck = BottleNecks(graph_mock)
        bottle_neck.ask_bottle_neck_questions = Mock()
        patch_ask.return_value = 1

        bottle_neck.ask_entry_point_question()

        patch_ask.assert_called_once_with(question, 1, 1)
        bottle_neck.ask_bottle_neck_questions.assert_called_once_with(entry_point_mock)
        graph_mock.add_resource_to_analyze.assert_called_once_with(entry_point_mock)

    def test_ask_bottle_neck_questions(self):
        my_resource = Mock()
        my_resource.get_resource_type.return_value = "AWS::Lambda::Function"

        graph_mock = Mock()
        bottle_neck = BottleNecks(graph_mock)
        bottle_neck.lambda_bottle_neck_quesitons = Mock()

        bottle_neck.ask_bottle_neck_questions(my_resource)

        bottle_neck.lambda_bottle_neck_quesitons.assert_called_once_with(my_resource)

    @patch("samcli.commands.check.bottle_necks.ask")
    def test_lambda_bottle_neck_quesitons(self, patch_ask):
        lambda_function_mock = Mock()
        lambda_function_mock.get_tps.return_value = -1

        patch_ask.return_value = Mock()

        graph_mock = Mock()
        bottle_neck = BottleNecks(graph_mock)

        bottle_neck.lambda_bottle_neck_quesitons(lambda_function_mock)

        patch_ask.assert_called()
        lambda_function_mock.set_tps.assert_called_once()
        lambda_function_mock.set_duration.assert_called_once_with(patch_ask.return_value)

        lambda_function_mock.get_tps.return_value = 500
        bottle_neck.lambda_bottle_neck_quesitons(lambda_function_mock)

        patch_ask.assert_called()
