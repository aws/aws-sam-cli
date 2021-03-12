import os
from unittest import TestCase
from samcli.lib.cookiecutter.interactive_flow_creator import InteractiveFlowCreator
from samcli.lib.cookiecutter.question import Question, QuestionKind


class TestInteractiveFlowCreator(TestCase):
    def test_create_flow(self):
        questions_path = os.path.join(os.path.dirname(__file__), "questions.yaml")
        flow = InteractiveFlowCreator.create_flow(flow_definition_path=questions_path)
        expected_flow_questions = {
            "1st": Question(
                key="1st",
                text="any text",
                options=None,
                default="",
                is_required=None,
                next_question_map={"*": "2nd"},
                kind=None,
            ),
            "2nd": Question(
                key="2nd",
                text="any text",
                options=["option1", "option2"],
                default="",
                is_required=None,
                next_question_map={"option1": "1st", "*": "3rd"},
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

    @staticmethod
    def assert_equal(q1: Question, q2: Question):
        assert q1.key == q2.key
        assert q1.text == q2.text
        assert q1.options == q2.options
        assert q1.default_answer == q2.default_answer
        assert q1.required == q2.required
        assert q1.next_question_map == q2.next_question_map
        assert q1.kind == q2.kind
