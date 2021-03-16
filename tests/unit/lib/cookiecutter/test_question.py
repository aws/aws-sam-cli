from unittest import TestCase
from samcli.lib.cookiecutter.question import Question, QuestionKind


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
    _ANY_KIND = QuestionKind.default

    def setUp(self):
        self.question = Question(
            text=self._ANY_TEXT,
            key=self._ANY_KEY,
            options=self._ANY_OPTIONS,
            default=self._ANY_ANSWER,
            is_required=True,
            next_question_map=self._ANY_NEXT_QUESTION_MAP,
            default_next_question_key=self._ANY_DEFAULT_NEXT_QUESTION_KEY,
            kind=self._ANY_KIND,
        )

    def test_creating_questions(self):
        q = Question(text=self._ANY_TEXT, key=self._ANY_KEY)
        self.assertEqual(q.text, self._ANY_TEXT)
        self.assertEqual(q.key, self._ANY_KEY)
        self.assertIsNone(q.options)
        self.assertEqual(q.default_answer, "")
        self.assertFalse(q.required)
        self.assertEqual(q.next_question_map, {})
        self.assertIsNone(q.default_next_question_key)
        self.assertEqual(q.kind, QuestionKind.default)

        q = self.question
        self.assertEqual(q.text, self._ANY_TEXT)
        self.assertEqual(q.key, self._ANY_KEY)
        self.assertEqual(q.options, self._ANY_OPTIONS)
        self.assertEqual(q.default_answer, self._ANY_ANSWER)
        self.assertTrue(q.required)
        self.assertEqual(q.next_question_map, self._ANY_NEXT_QUESTION_MAP)
        self.assertEqual(q.default_next_question_key, self._ANY_DEFAULT_NEXT_QUESTION_KEY)
        self.assertEqual(q.kind, self._ANY_KIND)

    def test_get_options_indexes_with_different_bases(self):
        indexes = self.question.get_options_indexes()
        self.assertEqual(indexes, [0, 1, 2])
        indexes = self.question.get_options_indexes(base=1)
        self.assertEqual(indexes, [1, 2, 3])
        q = Question(key=self._ANY_KEY, text=self._ANY_TEXT)
        indexes = q.get_options_indexes()
        self.assertEqual(indexes, [])

    def test_get_option(self):
        self.assertEqual(self.question.get_option(0), "option1")
        with self.assertRaises(ValueError):
            q = Question(key=self._ANY_KEY, text=self._ANY_TEXT)
            q.get_option(0)

    def test_get_next_question_key(self):
        self.assertEqual(self.question.get_next_question_key("option1"), "key1")
        self.assertEqual(self.question.get_next_question_key("option2"), "key2")
        self.assertEqual(self.question.get_next_question_key("option3"), "key3")
        self.assertEqual(self.question.get_next_question_key("any-option"), self._ANY_DEFAULT_NEXT_QUESTION_KEY)
        self.question.set_default_next_question_key("new_default")
        self.assertEqual(self.question.get_next_question_key(None), "new_default")
