from unittest import TestCase
from unittest.mock import patch
from samcli.lib.cookiecutter.interactive_flow import InteractiveFlow
from samcli.lib.cookiecutter.question import Question, QuestionKind


class TestInteractiveFlow(TestCase):
    _ANY_TEXT = "any text"
    _ANY_ANSWER = "any answer"
    _PARTICULAR_ANSWER = "particular answer"
    _FIRST_QUESTION = Question(key="1st", text=_ANY_TEXT, next_question_map={"*": "2nd"})
    _SECOND_QUESTION = Question(
        key="2nd", text=_ANY_TEXT, kind=QuestionKind.confirm, next_question_map={_PARTICULAR_ANSWER: "1st", "*": "3rd"}
    )
    _THIRD_QUESTION = Question(key="3rd", text=_ANY_TEXT, options=["option1", "option2"])
    _QUESTIONS = {"1st": _FIRST_QUESTION, "2nd": _SECOND_QUESTION, "3rd": _THIRD_QUESTION}

    def setUp(self) -> None:
        self.flow = InteractiveFlow(questions=self._QUESTIONS, first_question_key=self._FIRST_QUESTION.key)

    def test_create_interactive_flow(self):
        assert self.flow._questions == self._QUESTIONS
        assert self.flow._first_question_key == self._FIRST_QUESTION.key

    def test_get_next_question(self):
        assert self.flow.get_next_question() == self._FIRST_QUESTION
        assert self.flow.get_next_question(self._ANY_ANSWER) == self._SECOND_QUESTION
        assert self.flow.get_next_question(self._PARTICULAR_ANSWER) == self._FIRST_QUESTION
        assert self.flow.get_next_question(self._ANY_ANSWER) == self._SECOND_QUESTION
        assert self.flow.get_next_question(self._ANY_ANSWER) == self._THIRD_QUESTION
        assert self.flow.get_next_question(self._ANY_ANSWER) is None

    @patch.object(InteractiveFlow, "_ask_a_question")
    @patch.object(InteractiveFlow, "_ask_a_yes_no_question")
    @patch.object(InteractiveFlow, "_ask_a_multiple_choice_question")
    def test_run(self, mock_ask_a_multiple_choice_question, mock_ask_a_yes_no_question, mock_ask_a_question):
        mock_ask_a_question.return_value = "answer1"
        mock_ask_a_yes_no_question.return_value = False
        mock_ask_a_multiple_choice_question.return_value = "option1"
        expected_context = {"1st": "answer1", "2nd": False, "3rd": "option1"}
        initial_context = {}
        actual_context = self.flow.run(context=initial_context)
        mock_ask_a_question.assert_called_once_with(self._FIRST_QUESTION)
        mock_ask_a_yes_no_question.assert_called_once_with(self._SECOND_QUESTION)
        mock_ask_a_multiple_choice_question.assert_called_once_with(self._THIRD_QUESTION)
        assert expected_context == actual_context
        assert actual_context is not initial_context  # shouldn't modify the input, it should copy and return new
