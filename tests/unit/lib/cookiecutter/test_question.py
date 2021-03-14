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
        assert q.text == self._ANY_TEXT
        assert q.key == self._ANY_KEY
        assert q.options == []
        assert q.default_answer == ""
        assert q.required is False
        assert q.next_question_map == {}
        assert q.default_next_question_key is None
        assert q.kind == QuestionKind.default

        q = self.question
        assert q.text == self._ANY_TEXT
        assert q.key == self._ANY_KEY
        assert q.options == self._ANY_OPTIONS
        assert q.default_answer == self._ANY_ANSWER
        assert q.required is True
        assert q.next_question_map == self._ANY_NEXT_QUESTION_MAP
        assert q.default_next_question_key == self._ANY_DEFAULT_NEXT_QUESTION_KEY
        assert q.kind == self._ANY_KIND

    def test_get_choices_indexes_with_different_bases(self):
        indexes = self.question.get_choices_indexes()
        assert indexes == ["0", "1", "2"]
        indexes = self.question.get_choices_indexes(base=1)
        assert indexes == ["1", "2", "3"]

    def test_question_kind(self):
        assert self.question.is_mcq() is True
        self.question = Question(text=self._ANY_TEXT, key=self._ANY_KEY, kind=QuestionKind.confirm)
        assert self.question.is_yes_no() is True
        self.question = Question(text=self._ANY_TEXT, key=self._ANY_KEY, kind=QuestionKind.info)
        assert self.question.is_info() is True

    def test_get_option(self):
        assert self.question.get_option(0) == "option1"

    def test_get_next_question_key(self):
        assert self.question.get_next_question_key("option1") == "key1"
        assert self.question.get_next_question_key("option2") == "key2"
        assert self.question.get_next_question_key("option3") == "key3"
        assert self.question.get_next_question_key("any-option") == self._ANY_DEFAULT_NEXT_QUESTION_KEY
        self.question.set_default_next_question_key("new_default")
        assert self.question.get_next_question_key(None) == "new_default"
