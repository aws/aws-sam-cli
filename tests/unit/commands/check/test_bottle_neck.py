from unittest import TestCase
from unittest.mock import Mock, patch


from samcli.commands.check.bottle_necks import BottleNecks
from samcli.commands._utils.resources import AWS_LAMBDA_FUNCTION


class TestBottleNeck(TestCase):
    @patch("samcli.commands.check.bottle_necks.ask")
    @patch("samcli.commands.check.bottle_necks.click")
    def test_ask_entry_point_question(self, click_patch, patch_ask):
        graph_mock = Mock()
        entry_point_mock = Mock()
        entry_points = [entry_point_mock]

        entry_point_mock.resource_name = Mock()

        question = "We found the following resources in your application that could be the entry point for a request."

        question += "\n[%i] %s" % (1, entry_point_mock.resource_name) + "\nWhere should the simulation start?"

        graph_mock.entry_points = entry_points

        bottle_neck = BottleNecks(graph_mock)

        bottle_neck._ask_bottle_neck_questions = Mock()
        patch_ask.return_value = 1

        bottle_neck.ask_entry_point_question()

        patch_ask.assert_called_once_with(question, 1, 1)
        bottle_neck._ask_bottle_neck_questions.assert_called_once_with(entry_point_mock)
        graph_mock.resources_to_analyze.append.assert_called_once_with(entry_point_mock)

    def test_ask_bottle_neck_questions(self):
        my_resource = Mock()
        my_resource.resource_type = AWS_LAMBDA_FUNCTION

        graph_mock = Mock()
        bottle_neck = BottleNecks(graph_mock)
        bottle_neck._lambda_bottle_neck_quesitons = Mock()

        bottle_neck._ask_bottle_neck_questions(my_resource)

        bottle_neck._lambda_bottle_neck_quesitons.assert_called_once_with(my_resource)

    @patch("samcli.commands.check.bottle_necks.ask")
    def test__lambda_bottle_neck_quesitons(self, patch_ask):
        lambda_function_mock = Mock()
        lambda_function_mock.tps = -1
        lambda_function_mock.duration = -1

        patch_ask.return_value = Mock()

        graph_mock = Mock()
        bottle_neck = BottleNecks(graph_mock)

        bottle_neck._lambda_bottle_neck_quesitons(lambda_function_mock)

        patch_ask.assert_called()
        self.assertEqual(lambda_function_mock.tps, patch_ask.return_value)

        bottle_neck._lambda_bottle_neck_quesitons(lambda_function_mock)

        patch_ask.assert_called()
        self.assertEqual(lambda_function_mock.duration, patch_ask.return_value)
