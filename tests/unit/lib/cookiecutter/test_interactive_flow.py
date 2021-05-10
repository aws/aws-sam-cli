from pathlib import Path
from unittest import TestCase
from unittest.mock import patch
from samcli.lib.cookiecutter.interactive_flow import InteractiveFlow
from samcli.lib.cookiecutter.question import Question, Choice, Confirm


class TestInteractiveFlow(TestCase):
    _ANY_KEY = "any key"
    _ANY_TEXT = "any text"
    _ANY_ANSWER = "any answer"
    _PARTICULAR_ANSWER = "particular answer"
    _FIRST_QUESTION = Question(key="1st", text=_ANY_TEXT, default_next_question_key="2nd")
    _SECOND_QUESTION = Confirm(
        key="2nd",
        text=_ANY_TEXT,
        next_question_map={_PARTICULAR_ANSWER: "1st"},
        default_next_question_key="3rd",
    )
    _THIRD_QUESTION = Choice(key="3rd", text=_ANY_TEXT, options=["option1", "option2"])
    _QUESTIONS = {"1st": _FIRST_QUESTION, "2nd": _SECOND_QUESTION, "3rd": _THIRD_QUESTION}

    def setUp(self) -> None:
        self.flow = InteractiveFlow(questions=self._QUESTIONS, first_question_key=self._FIRST_QUESTION.key)

    def test_create_interactive_flow(self):
        self.assertEqual(self.flow._questions, self._QUESTIONS)
        self.assertEqual(self.flow._first_question_key, self._FIRST_QUESTION.key)

    def test_advance_to_next_question(self):
        self.assertEqual(self.flow.advance_to_next_question(), self._FIRST_QUESTION)
        self.assertEqual(self.flow.advance_to_next_question(self._ANY_ANSWER), self._SECOND_QUESTION)
        self.assertEqual(self.flow.advance_to_next_question(self._PARTICULAR_ANSWER), self._FIRST_QUESTION)
        self.assertEqual(self.flow.advance_to_next_question(self._ANY_ANSWER), self._SECOND_QUESTION)
        self.assertEqual(self.flow.advance_to_next_question(self._ANY_ANSWER), self._THIRD_QUESTION)
        self.assertIsNone(self.flow.advance_to_next_question(self._ANY_ANSWER))

    @patch.object(Question, "ask")
    @patch.object(Confirm, "ask")
    @patch.object(Choice, "ask")
    def test_run(self, mock_3rd_q, mock_2nd_q, mock_1st_q):
        mock_1st_q.return_value = "answer1"
        mock_2nd_q.return_value = False
        mock_3rd_q.return_value = "option1"
        expected_context = {"1st": "answer1", "2nd": False, "3rd": "option1"}
        initial_context = {}
        actual_context = self.flow.run(context=initial_context)
        mock_1st_q.assert_called_once()
        mock_2nd_q.assert_called_once()
        mock_3rd_q.assert_called_once()
        self.assertEqual(expected_context, actual_context)
        self.assertIsNot(actual_context, initial_context)  # shouldn't modify the input, it should copy and return new

    @patch.object(Question, "ask")
    @patch.object(Confirm, "ask")
    @patch.object(Choice, "ask")
    def test_run_with_preloaded_default_values(self, mock_3rd_q, mock_2nd_q, mock_1st_q):

        mock_1st_q.return_value = "answer1"
        mock_2nd_q.return_value = False
        mock_3rd_q.return_value = "option1"

        initial_context = {"key": "value", "['beta', 'bootstrap', 'x']": "y"}

        actual_context = self.flow.run(initial_context)

        mock_1st_q.assert_called_once()
        mock_2nd_q.assert_called_once()
        mock_3rd_q.assert_called_once()

        self.assertEqual(
            {"1st": "answer1", "2nd": False, "3rd": "option1", "['beta', 'bootstrap', 'x']": "y", "key": "value"},
            actual_context,
        )
        self.assertIsNot(actual_context, initial_context)  # shouldn't modify the input, it should copy and return new
