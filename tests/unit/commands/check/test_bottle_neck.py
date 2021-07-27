from unittest import TestCase
from unittest.mock import Mock, patch

from boto3 import resource

from samcli.commands.check.bottle_necks import BottleNecks


class TestBottleNeck(TestCase):
    @patch("samcli.commands.check.bottle_necks.click")
    def test_ask(self, click_patch):
        click_patch.prompt.return_value = 5
        question = "question"
        result = BottleNecks.ask(Mock(), question, 1, 10)

        self.assertEqual(result, click_patch.prompt.return_value)
        click_patch.prompt.assert_called_with(text=question, type=int)

    @patch("samcli.commands.check.bottle_necks.click")
    def test_ask_entry_point_question(self, click_patch):
        graph_mock = Mock()
        entry_point_mock = Mock()
        entry_points = [entry_point_mock]

        entry_point_mock.get_name.return_value = Mock()

        question = "We found the following resources in your application that could be the entry point for a request."

        question += "\n[%i] %s" % (1, entry_point_mock.get_name.return_value) + "\nWhere should the simulation start?"

        graph_mock.get_entry_points.return_value = entry_points

        bottle_neck = BottleNecks(graph_mock)
        bottle_neck.ask = Mock()
        bottle_neck.ask.return_value = 1

        bottle_neck.ask_bottle_neck_questions = Mock()

        bottle_neck.ask_entry_point_question()

        bottle_neck.ask.assert_called_once_with(question, 1, 1)
        bottle_neck.ask_bottle_neck_questions.assert_called_once_with(entry_point_mock)

    def test_ask_bottle_neck_questions(self):
        self_mock = Mock()
        my_resource = None

        self_mock.lambda_bottle_neck_quesitons.return_value = Mock()
        self_mock.event_source_bottle_neck_questions.return_value = Mock()

        my_resource = Mock()
        my_resource.get_resource_type.return_value = "AWS::Lambda::Function"

        BottleNecks.ask_bottle_neck_questions(self_mock, my_resource)
        self_mock.lambda_bottle_neck_quesitons.assert_called_with(my_resource)

        my_resource.get_resource_type.return_value = "AWS::ApiGateway::RestApi"
        BottleNecks.ask_bottle_neck_questions(self_mock, my_resource)
        self_mock.event_source_bottle_neck_questions.assert_called_with(my_resource)

    def test_event_source_bottle_neck_questions(self):
        self_mock = Mock()
        event_source_mock = Mock()
        child_mock = Mock()
        input_mock = Mock()

        event_source_mock.set_tps.return_value = Mock()
        event_source_mock.get_children.return_value = [child_mock]
        event_source_mock.get_parents.return_value = []
        child_mock.set_tps.return_value = Mock()

        self_mock.ask.return_value = input_mock
        self_mock.ask_bottle_neck_questions.return_value = Mock()
        self_mock.ask_bottle_neck_questions.return_value = Mock()

        BottleNecks.event_source_bottle_neck_questions(self_mock, event_source_mock)

        self_mock.ask.assert_called_once()
        self_mock.ask_bottle_neck_questions.assert_called_once_with(child_mock)
        event_source_mock.set_tps.assert_called_once_with(input_mock)
        child_mock.set_tps.assert_called_once_with(input_mock)

    def test_lambda_bottle_neck_quesitons(self):
        self_mock = Mock()
        lambda_function_mock = Mock()
        lambda_function_mock.get_tps.return_value = None
        child_mock = Mock()
        lambda_function_mock.get_children.return_value = [child_mock]

        self_mock.ask.return_value = Mock()
        self_mock.ask_bottle_neck_questions.return_value = Mock()

        BottleNecks.lambda_bottle_neck_quesitons(self_mock, lambda_function_mock)

        self_mock.ask.assert_called()
        lambda_function_mock.set_tps.assert_called_once()
        lambda_function_mock.set_duration.assert_called_once_with(self_mock.ask.return_value)
        lambda_function_mock.get_children.assert_called_once()
        self_mock.ask_bottle_neck_questions.assert_called_once_with(child_mock)

        # Need to reset self_mock.ask call amount by reseting mock
        self_mock = Mock()
        lambda_function_mock.get_tps.return_value = "Not None"
        BottleNecks.lambda_bottle_neck_quesitons(self_mock, lambda_function_mock)

        self_mock.ask.assert_called_once()
