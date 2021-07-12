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

        """ side effect
            click_patch.prompt.side_effect[11, -4, 5]
            check if click.echo is called with ("message") 2 times
        """

    # def ask(self, question, min=1, max=float("inf")):
    #     valid_user_input = False
    #     user_input = None
    #     while valid_user_input is False:
    #         user_input = click.prompt(text=question, type=int)
    #         if user_input > max or user_input < min:
    #             click.echo("Please enter a number within the range")
    #         else:
    #             valid_user_input = True

    #     return user_input

    @patch("samcli.commands.check.bottle_necks.click")
    def test_ask_entry_point_question(self, click_patch):
        self_mock = Mock()
        entry_point_mock = Mock()

        entry_point_mock.get_name.return_value = Mock()
        entry_point_mock.pop.return_value = Mock()
        self_mock.ask.return_value = 1

        self_mock.graph.get_entry_points.return_value = [entry_point_mock]

        entry_point_question = (
            "We found the following resources in your application that could be the entry point for a request."
        )
        entry_point_question += "\n[%i] %s" % (1, entry_point_mock.get_name)
        entry_point_question += "\nWhere should the simulation start?"

        result = BottleNecks.ask_entry_point_question(self_mock)

        self_mock.ask.assert_called_with(entry_point_question, 1, 1)
        # self_mock.ask.assert_called_once()

        # entry_point_mock.pop.assert_called_once_with(self_mock.ask)

        # self_mock.ask_bottle_neck_questions.assert_called_with(entry_point_mock.pop)
        # self_mock.graph.add_resource_to_analyze.assert_called_with(entry_point_mock.pop)

    # def ask_entry_point_question(self):
    #     entry_points = self.graph.get_entry_points()

    #     # All entry points must be calcualted before info can be displayed
    #     while entry_points != []:
    #         entry_point_question = (
    #             "We found the following resources in your application that could be the entry point for a request."
    #         )
    #         item_number = 1
    #         for item in entry_points:
    #             item_name = item.get_name()
    #             entry_point_question += "\n[%i] %s" % (item_number, item_name)
    #             item_number += 1

    #         entry_point_question += "\nWhere should the simulation start?"
    #         user_input = self.ask(entry_point_question, 1, item_number - 1)

    #         current_entry_point = entry_points.pop(user_input - 1)

    #         self.ask_bottle_neck_questions(current_entry_point)

    #         self.graph.add_resource_to_analyze(current_entry_point)

    #     click.echo("Running calculations...")

    #     return

    def test_ask_bottle_neck_questions(self):
        self_mock = Mock()
        my_resource = None

        result = BottleNecks.ask_bottle_neck_questions(self_mock, my_resource)

        # ensure method returns None if resource is None
        self.assertEqual(result, my_resource)

        my_resource = Mock()
        my_resource.get_resource_type.return_value = "AWS::Lambda::Function"

        result = BottleNecks.ask_bottle_neck_questions(self_mock, my_resource)

        self_mock.lambda_bottle_neck_quesitons.assert_called_with(my_resource)

    # def ask_bottle_neck_questions(self, resource):
    #     if resource is None:
    #         return

    #     if resource.get_resource_type() == "AWS::Lambda::Function":
    #         self.lambda_bottle_neck_quesitons(resource)

    def test_lambda_bottle_neck_quesitons(self):
        self_mock = Mock()
        lambda_function_mock = Mock()
        lambda_function_mock.get_tps.return_value = None

        self_mock.ask.return_value = Mock()

        result = BottleNecks.lambda_bottle_neck_quesitons(self_mock, lambda_function_mock)

        self_mock.ask.assert_called()
        lambda_function_mock.set_tps.assert_called_once()
        lambda_function_mock.set_duration.assert_called_once_with(self_mock.ask.return_value)

        # Need to reset self_mock.ask call amount by reseting mock
        self_mock = Mock()
        lambda_function_mock.get_tps.return_value = "Not None"
        result = BottleNecks.lambda_bottle_neck_quesitons(self_mock, lambda_function_mock)

        self_mock.ask.assert_called_once()

    # def lambda_bottle_neck_quesitons(self, lambda_function):
    #     # If there is no entry point to the lambda function, get tps
    #     if lambda_function.get_tps() is None:
    #         user_input_tps = self.ask(
    #             "What is the expected per-second arrival rate for [%s]?\n[TPS]" % (lambda_function.get_name())
    #         )
    #         lambda_function.set_tps(user_input_tps)

    #     user_input_duration = self.ask(
    #         "What is the expected duration for the Lambda function [%s] in ms?\n[1 - 900,000]"
    #         % (lambda_function.get_name()),
    #         1,
    #         900000,
    #     )

    #     lambda_function.set_duration(user_input_duration)
