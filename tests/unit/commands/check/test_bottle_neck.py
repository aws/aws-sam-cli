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
        self_mock = Mock()
        my_resource = None
        entry_point_name = Mock()

        self_mock.lambda_bottle_neck_quesitons.return_value = Mock()
        self_mock.event_source_bottle_neck_questions.return_value = Mock()

        my_resource = Mock()
        my_resource.get_resource_type.return_value = "AWS::Lambda::Function"

        BottleNecks.ask_bottle_neck_questions(self_mock, my_resource, entry_point_name)
        self_mock.lambda_bottle_neck_quesitons.assert_called_with(my_resource, entry_point_name)

        my_resource.get_resource_type.return_value = "AWS::ApiGateway::RestApi"
        BottleNecks.ask_bottle_neck_questions(self_mock, my_resource, entry_point_name)
        self_mock.event_source_bottle_neck_questions.assert_called_with(my_resource, entry_point_name)

    def test_event_source_bottle_neck_questions(self):
        self_mock = Mock()
        event_source_mock = Mock()
        child_mock = Mock()
        input_mock = Mock()
        entry_point_name = Mock()

        event_source_mock.set_tps.return_value = Mock()
        event_source_mock.get_children.return_value = [child_mock]
        event_source_mock.get_parents.return_value = []
        child_mock.set_tps.return_value = Mock()

        self_mock.ask.return_value = input_mock
        self_mock.ask_bottle_neck_questions.return_value = Mock()
        self_mock.ask_bottle_neck_questions.return_value = Mock()

        BottleNecks.event_source_bottle_neck_questions(self_mock, event_source_mock, entry_point_name)

        self_mock.ask.assert_called_once()
        self_mock.ask_bottle_neck_questions.assert_called_once_with(child_mock, entry_point_name)
        event_source_mock.set_tps.assert_called_once_with(input_mock)
        child_mock.set_tps.assert_called_once_with(input_mock)

    @patch("samcli.commands.check.bottle_necks.ask")
    def test_lambda_bottle_neck_quesitons(self, patch_ask):
        self_mock = Mock()
        self_mock.graph.resources_to_analyze = {}

        lambda_function_mock = Mock()
        lambda_function_mock.get_tps.return_value = None

        child_mock = Mock()
        lambda_function_mock.get_children.return_value = [child_mock]

        copy_lambda_function_mock = Mock()
        copy_lambda_function_mock.resource_name = ""
        lambda_function_mock.copy_data.return_value = copy_lambda_function_mock

        entry_point_name = "Mock"

        self_mock.ask.return_value = Mock()
        self_mock.ask_bottle_neck_questions.return_value = Mock()

        BottleNecks.lambda_bottle_neck_quesitons(self_mock, lambda_function_mock, entry_point_name)

        self_mock.ask.assert_called()
        lambda_function_mock.set_tps.assert_called_once()
        lambda_function_mock.set_duration.assert_called_once_with(self_mock.ask.return_value)
        lambda_function_mock.get_children.assert_called_once()
        self_mock.ask_bottle_neck_questions.assert_called_once_with(child_mock, entry_point_name)

        # Need to reset self_mock.ask call amount by reseting mock
        self_mock = Mock()
        self_mock.graph.resources_to_analyze = {}
        lambda_function_mock.get_tps.return_value = "Not None"
        BottleNecks.lambda_bottle_neck_quesitons(self_mock, lambda_function_mock, entry_point_name)

        self_mock.ask.assert_called_once()
