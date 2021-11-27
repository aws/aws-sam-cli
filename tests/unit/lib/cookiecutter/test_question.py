from typing import List, Union, Dict
from unittest import TestCase
from unittest.mock import ANY, patch, Mock

from parameterized import parameterized

from samcli.lib.cookiecutter.question import Question, QuestionKind, Choice, Confirm, Info, QuestionFactory


class TestQuestion(TestCase):

    _ANY_TEXT = "any text"
    _ANY_KEY = "any key"
    _ANY_OPTIONS = ["option1", "option2", "option3"]
    _ANY_ANSWER = "any answer"
    _ANY_NEXT_QUESTION_MAP = {
        "option1": "key1",
        "option2": "key2",
        "option3": "key3",
    }
    _ANY_DEFAULT_NEXT_QUESTION_KEY = "default"
    _ANY_KIND = QuestionKind.question

    def setUp(self):
        self.question = Question(
            text=self._ANY_TEXT,
            key=self._ANY_KEY,
            default=self._ANY_ANSWER,
            is_required=True,
            allow_autofill=False,
            next_question_map=self._ANY_NEXT_QUESTION_MAP,
            default_next_question_key=self._ANY_DEFAULT_NEXT_QUESTION_KEY,
        )

    def get_question_with_default_from_cookiecutter_context_using_keypath(
        self, key_path: List[Union[str, Dict]]
    ) -> Question:
        return Question(
            text=self._ANY_TEXT,
            key=self._ANY_KEY,
            default={"keyPath": key_path},
            is_required=True,
            next_question_map=self._ANY_NEXT_QUESTION_MAP,
            default_next_question_key=self._ANY_DEFAULT_NEXT_QUESTION_KEY,
        )

    def test_creating_questions(self):
        q = Question(text=self._ANY_TEXT, key=self._ANY_KEY)
        self.assertEqual(q.text, self._ANY_TEXT)
        self.assertEqual(q.key, self._ANY_KEY)
        self.assertEqual(q.default_answer, "")
        self.assertFalse(q.required)
        self.assertEqual(q.next_question_map, {})
        self.assertIsNone(q.default_next_question_key)

        q = self.question
        self.assertEqual(q.text, self._ANY_TEXT)
        self.assertEqual(q.key, self._ANY_KEY)
        self.assertEqual(q.default_answer, self._ANY_ANSWER)
        self.assertTrue(q.required)
        self.assertEqual(q.next_question_map, self._ANY_NEXT_QUESTION_MAP)
        self.assertEqual(q.default_next_question_key, self._ANY_DEFAULT_NEXT_QUESTION_KEY)

    def test_question_key_and_text_are_required(self):
        with (self.assertRaises(TypeError)):
            Question(text=self._ANY_TEXT)
        with (self.assertRaises(TypeError)):
            Question(key=self._ANY_KEY)

    def test_get_next_question_key(self):
        self.assertEqual(self.question.get_next_question_key("option1"), "key1")
        self.assertEqual(self.question.get_next_question_key("option2"), "key2")
        self.assertEqual(self.question.get_next_question_key("option3"), "key3")
        self.assertEqual(self.question.get_next_question_key("any-option"), self._ANY_DEFAULT_NEXT_QUESTION_KEY)
        self.question.set_default_next_question_key("new_default")
        self.assertEqual(self.question.get_next_question_key(None), "new_default")

    @patch("samcli.lib.cookiecutter.question.click")
    def test_ask(self, mock_click):
        mock_click.prompt.return_value = self._ANY_ANSWER
        answer = self.question.ask({})
        self.assertEqual(answer, self._ANY_ANSWER)
        mock_click.prompt.assert_called_once_with(text=self.question.text, default=self.question.default_answer)

    @patch("samcli.lib.cookiecutter.question.click")
    def test_ask_resolves_from_cookiecutter_context(self, mock_click):
        # Setup
        expected_default_value = Mock()
        previous_question_key = "this is a question"
        previous_question_answer = "this is an answer"
        context = {
            "['x', 'this is an answer']": expected_default_value,
            previous_question_key: previous_question_answer,
        }
        question = self.get_question_with_default_from_cookiecutter_context_using_keypath(
            ["x", {"valueOf": previous_question_key}]
        )

        # Trigger
        question.ask(context=context)

        # Verify
        mock_click.prompt.assert_called_once_with(text=self.question.text, default=expected_default_value)

    @patch("samcli.lib.cookiecutter.question.click")
    def test_ask_resolves_from_cookiecutter_context_non_exist_key_path(self, mock_click):
        # Setup
        context = {}
        question = self.get_question_with_default_from_cookiecutter_context_using_keypath(["y"])

        # Trigger
        question.ask(context=context)

        # Verify
        mock_click.prompt.assert_called_once_with(text=self.question.text, default=None)

    def test_ask_resolves_from_cookiecutter_context_non_exist_question_key(self):
        # Setup
        expected_default_value = Mock()
        previous_question_key = "this is a question"
        previous_question_answer = "this is an answer"
        context = {
            "['x', 'this is an answer']": expected_default_value,
            previous_question_key: previous_question_answer,
        }
        question = self.get_question_with_default_from_cookiecutter_context_using_keypath(
            ["x", {"valueOf": "non_exist_question_key"}]
        )

        # Trigger
        with self.assertRaises(KeyError):
            question.ask(context=context)

    @parameterized.expand([("this should have been a list"), ([1],), ({},)])
    def test_ask_resolves_from_cookiecutter_context_with_key_path_not_a_list(self, key_path):
        # Setup
        context = {}
        question = self.get_question_with_default_from_cookiecutter_context_using_keypath(key_path)

        # Trigger
        with self.assertRaises(ValueError):
            question.ask(context=context)

    @parameterized.expand([({"keyPath123": Mock()},), ({"keyPath": [{"valueOf123": Mock()}]},)])
    def test_ask_resolves_from_cookiecutter_context_with_default_object_missing_keys(self, default_object):
        # Setup
        context = {}
        question = self.get_question_with_default_from_cookiecutter_context_using_keypath([])
        question._default_answer = default_object

        # Trigger
        with self.assertRaises(KeyError):
            question.ask(context=context)

    def test_question_allow_autofill_with_default_value(self):
        q = Question(text=self._ANY_TEXT, key=self._ANY_KEY, is_required=True, allow_autofill=True, default="123")
        self.assertEquals("123", q.ask())

    @patch("samcli.lib.cookiecutter.question.click")
    def test_question_allow_autofill_without_default_value(self, click_mock):
        answer_mock = click_mock.prompt.return_value = Mock()
        q = Question(text=self._ANY_TEXT, key=self._ANY_KEY, is_required=True, allow_autofill=True)
        self.assertEquals(answer_mock, q.ask())


class TestChoice(TestCase):
    def setUp(self):
        self.question = Choice(
            text=TestQuestion._ANY_TEXT,
            key=TestQuestion._ANY_KEY,
            options=TestQuestion._ANY_OPTIONS,
            default=TestQuestion._ANY_ANSWER,
            is_required=True,
            next_question_map=TestQuestion._ANY_NEXT_QUESTION_MAP,
            default_next_question_key=TestQuestion._ANY_DEFAULT_NEXT_QUESTION_KEY,
        )

    def test_create_choice_question(self):
        self.assertEqual(self.question.text, TestQuestion._ANY_TEXT)
        self.assertEqual(self.question.key, TestQuestion._ANY_KEY)
        self.assertEqual(self.question._options, TestQuestion._ANY_OPTIONS)
        with (self.assertRaises(TypeError)):
            Choice(key=TestQuestion._ANY_KEY, text=TestQuestion._ANY_TEXT)
        with (self.assertRaises(ValueError)):
            Choice(key=TestQuestion._ANY_KEY, text=TestQuestion._ANY_TEXT, options=None)
        with (self.assertRaises(ValueError)):
            Choice(key=TestQuestion._ANY_KEY, text=TestQuestion._ANY_TEXT, options=[])

    def test_get_options_indexes_with_different_bases(self):
        indexes = self.question._get_options_indexes()
        self.assertEqual(indexes, [0, 1, 2])
        indexes = self.question._get_options_indexes(base=1)
        self.assertEqual(indexes, [1, 2, 3])

    @patch("samcli.lib.cookiecutter.question.click.Choice")
    @patch("samcli.lib.cookiecutter.question.click")
    def test_ask(self, mock_click, mock_choice):
        mock_click.prompt.return_value = 2
        answer = self.question.ask({})
        self.assertEqual(answer, TestQuestion._ANY_OPTIONS[1])  # we deduct one from user's choice (base 1 vs base 0)
        mock_click.prompt.assert_called_once_with(
            text="Choice",
            default=self.question.default_answer,
            show_choices=False,
            type=ANY,
            show_default=self.question.default_answer is not None,
        )
        mock_choice.assert_called_once_with(["1", "2", "3"])


class TestInfo(TestCase):
    @patch("samcli.lib.cookiecutter.question.click")
    def test_ask(self, mock_click):
        q = Info(text=TestQuestion._ANY_TEXT, key=TestQuestion._ANY_KEY)
        mock_click.echo.return_value = None
        answer = q.ask({})
        self.assertIsNone(answer)
        mock_click.echo.assert_called_once_with(message=q.text)


class TestConfirm(TestCase):
    @patch("samcli.lib.cookiecutter.question.click")
    def test_ask(self, mock_click):
        q = Confirm(text=TestQuestion._ANY_TEXT, key=TestQuestion._ANY_KEY)
        mock_click.confirm.return_value = True
        answer = q.ask({})
        self.assertTrue(answer)
        mock_click.confirm.assert_called_once_with(text=q.text)


class TestQuestionFactory(TestCase):
    def test_there_is_a_handler_for_each_question_kind(self):
        question_json = {"key": TestQuestion._ANY_KEY, "question": TestQuestion._ANY_TEXT, "options": ["a", "b"]}
        for kind in QuestionKind:
            question_json["kind"] = kind.name
            q = QuestionFactory.create_question_from_json(question_json)
            expected_type = QuestionFactory.question_classes[kind]
            self.assertTrue(isinstance(q, expected_type))
