import os
from unittest import TestCase
from unittest.mock import patch
from samcli.lib.cookiecutter.interactive_flow_creator import (
    InteractiveFlowCreator,
    QuestionsNotFoundException,
    QuestionsFailedParsingException,
)
from samcli.lib.cookiecutter.question import Question, Choice, Confirm


class TestInteractiveFlowCreator(TestCase):
    def test_create_flow(self):
        questions_path = os.path.join(os.path.dirname(__file__), "questions.json")
        flow = InteractiveFlowCreator.create_flow(flow_definition_path=questions_path, extra_context={"X": "xVal"})
        expected_flow_questions = {
            "1st": Question(
                key="1st",
                text="any text with variable X substitution to xVal",
                default="",
                is_required=None,
                default_next_question_key="2nd",
            ),
            "2nd": Choice(
                key="2nd",
                text="any text",
                options=["option1", "option2"],
                default="",
                is_required=None,
                next_question_map={"option1": "1st"},
                default_next_question_key="3rd",
            ),
            "3rd": Confirm(
                key="3rd",
                text="any text",
                default=None,
                is_required=True,
                next_question_map=None,
            ),
        }

        self.assertEqual(flow._questions["1st"].__dict__, expected_flow_questions["1st"].__dict__)
        self.assertEqual(flow._questions["2nd"].__dict__, expected_flow_questions["2nd"].__dict__)
        self.assertEqual(flow._questions["3rd"].__dict__, expected_flow_questions["3rd"].__dict__)

    def test_questions_definition_file_not_found_exception(self):
        with self.assertRaises(QuestionsNotFoundException):
            questions_path = os.path.join(os.path.dirname(__file__), "not-existing-file.yaml")
            InteractiveFlowCreator.create_flow(flow_definition_path=questions_path)

    @patch("samcli.lib.cookiecutter.interactive_flow_creator.parse_yaml_file")
    def test_parsing_exceptions_of_questions_definition_parsing(self, mock_parse_yaml_file):
        with self.assertRaises(QuestionsFailedParsingException):
            questions_path = os.path.join(os.path.dirname(__file__), "questions.json")
            mock_parse_yaml_file.side_effect = ValueError
            InteractiveFlowCreator.create_flow(flow_definition_path=questions_path)
