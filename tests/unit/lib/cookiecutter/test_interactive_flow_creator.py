import os
from unittest import TestCase
from unittest.mock import patch
from samcli.lib.cookiecutter.interactive_flow_creator import (
    InteractiveFlowCreator,
    QuestionsNotFoundException,
    QuestionsFailedParsingException,
)
from samcli.lib.cookiecutter.question import Question, QuestionKind


class TestInteractiveFlowCreator(TestCase):
    def test_create_flow(self):
        questions_path = os.path.join(os.path.dirname(__file__), "questions.yaml")
        flow = InteractiveFlowCreator.create_flow(flow_definition_path=questions_path, extra_context={"X": "xVal"})
        expected_flow_questions = {
            "1st": Question(
                key="1st",
                text="any text with variable X substitution to xVal",
                options=None,
                default="",
                is_required=None,
                default_next_question_key="2nd",
                kind=None,
            ),
            "2nd": Question(
                key="2nd",
                text="any text",
                options=["option1", "option2"],
                default="",
                is_required=None,
                next_question_map={"option1": "1st"},
                default_next_question_key="3rd",
                kind=None,
            ),
            "3rd": Question(
                key="3rd",
                text="any text",
                options=None,
                default=None,
                is_required=True,
                next_question_map=None,
                kind=QuestionKind.confirm,
            ),
        }

        self.assert_equal(flow._questions["1st"], expected_flow_questions["1st"])
        self.assert_equal(flow._questions["2nd"], expected_flow_questions["2nd"])
        self.assert_equal(flow._questions["3rd"], expected_flow_questions["3rd"])

    def test_questions_definition_file_not_found_exception(self):
        with self.assertRaises(QuestionsNotFoundException):
            questions_path = os.path.join(os.path.dirname(__file__), "not-existing-file.yaml")
            InteractiveFlowCreator.create_flow(flow_definition_path=questions_path)

    @patch("samcli.lib.cookiecutter.interactive_flow_creator.parse_yaml_file")
    def test_parsing_exceptions_of_questions_definition_parsing(self, mock_parse_yaml_file):
        with self.assertRaises(QuestionsFailedParsingException):
            questions_path = os.path.join(os.path.dirname(__file__), "questions.yaml")
            mock_parse_yaml_file.side_effect = ValueError
            InteractiveFlowCreator.create_flow(flow_definition_path=questions_path)

    def assert_equal(self, q1: Question, q2: Question):
        self.assertEqual(q1.key, q2.key)
        self.assertEqual(q1.text, q2.text)
        self.assertEqual(q1.options, q2.options)
        self.assertEqual(q1.default_answer, q2.default_answer)
        self.assertEqual(q1.required, q2.required)
        self.assertEqual(q1.next_question_map, q2.next_question_map)
        self.assertEqual(q1.kind, q2.kind)
