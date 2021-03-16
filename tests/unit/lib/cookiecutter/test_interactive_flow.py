from unittest import TestCase
from unittest.mock import patch, ANY
from samcli.lib.cookiecutter.interactive_flow import InteractiveFlow
from samcli.lib.cookiecutter.question import Question, QuestionKind


class TestInteractiveFlow(TestCase):
    _ANY_KEY = "any key"
    _ANY_TEXT = "any text"
    _ANY_ANSWER = "any answer"
    _PARTICULAR_ANSWER = "particular answer"
    _FIRST_QUESTION = Question(key="1st", text=_ANY_TEXT, default_next_question_key="2nd")
    _SECOND_QUESTION = Question(
        key="2nd",
        text=_ANY_TEXT,
        kind=QuestionKind.confirm,
        next_question_map={_PARTICULAR_ANSWER: "1st"},
        default_next_question_key="3rd",
    )
    _THIRD_QUESTION = Question(key="3rd", text=_ANY_TEXT, options=["option1", "option2"])
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
        self.assertEqual(expected_context, actual_context)
        self.assertIsNot(actual_context, initial_context)  # shouldn't modify the input, it should copy and return new

    @patch("samcli.lib.cookiecutter.interactive_flow.click")
    def test_there_is_a_handler_for_each_question_kind(self, mock_click):
        for kind in QuestionKind:
            q = Question(key=self._ANY_KEY, text=self._ANY_TEXT, kind=kind, options=["opt1", "opt2"])
            flow = InteractiveFlow(questions={q.key: q}, first_question_key=self._ANY_KEY)
            # if a handler of a QuestionKind is missing, then an exception will be raised while running the flow
            flow.run(context={})

    @patch("samcli.lib.cookiecutter.interactive_flow.click")
    def test_echo(self, mock_click):
        self.flow._echo(Question(key="any", text=self._ANY_TEXT))
        mock_click.echo.assert_called_once_with(message=self._ANY_TEXT)

    @patch("samcli.lib.cookiecutter.interactive_flow.click")
    def test_ask_a_question(self, mock_click):
        self.flow._ask_a_question(Question(key="any", text=self._ANY_TEXT))
        mock_click.prompt.assert_called_once_with(text=self._ANY_TEXT, default="")
        mock_click.reset_mock()
        self.flow._ask_a_question(Question(key="any", text=self._ANY_TEXT, is_required=True))
        mock_click.prompt.assert_called_once_with(text=self._ANY_TEXT, default=None)
        mock_click.reset_mock()
        self.flow._ask_a_question(Question(key="any", text=self._ANY_TEXT, default="any default answer"))
        mock_click.prompt.assert_called_once_with(text=self._ANY_TEXT, default="any default answer")

    @patch("samcli.lib.cookiecutter.interactive_flow.click")
    def test_ask_a_yes_no_question(self, mock_click):
        self.flow._ask_a_yes_no_question(Question(key="any", text=self._ANY_TEXT))
        mock_click.confirm.assert_called_once_with(text=self._ANY_TEXT, default="")
        mock_click.reset_mock()
        self.flow._ask_a_yes_no_question(Question(key="any", text=self._ANY_TEXT, is_required=True))
        mock_click.confirm.assert_called_once_with(text=self._ANY_TEXT, default=None)

    @patch("samcli.lib.cookiecutter.interactive_flow.click.Choice")
    @patch("samcli.lib.cookiecutter.interactive_flow.click")
    def test_ask_a_multiple_choice_question(self, mock_click, mock_choice):
        self.flow._ask_a_multiple_choice_question(Question(key="any", text=self._ANY_TEXT, options=["opt1", "opt2"]))
        mock_click.prompt.assert_called_once_with(text="Choice", default="", show_choices=False, type=ANY)
        mock_choice.assert_called_once_with(["1", "2"])
