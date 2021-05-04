from unittest import TestCase
from unittest.mock import ANY, patch, Mock
from samcli.lib.cookiecutter.question import Question, QuestionKind, Choice, Confirm, Info, QuestionFactory
from samcli.lib.config.samconfig import SamConfig, DEFAULT_ENV


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

    _ANY_TOML_FILE = "any/file.toml"
    _ANY_EXTRA_CONTEXT_KEY = "any key from extra context (previous questions keys)"
    _ANY_EXTRA_CONTEXT_VALUE = "any value from extra context (previous questions answers)"
    _ANY_COMMAND_NAMES = "any_command_names"
    _ANY_SECTION = "any section"
    _ANY_TOML_ANSWER = "any toml answer"

    def setUp(self):
        self.question = Question(
            text=self._ANY_TEXT,
            key=self._ANY_KEY,
            default=self._ANY_ANSWER,
            is_required=True,
            next_question_map=self._ANY_NEXT_QUESTION_MAP,
            default_next_question_key=self._ANY_DEFAULT_NEXT_QUESTION_KEY,
        )

    def get_question_with_default_from_toml(self):
        return Question(
            text=self._ANY_TEXT,
            key=self._ANY_KEY,
            default=self._ANY_ANSWER,
            is_required=True,
            next_question_map=self._ANY_NEXT_QUESTION_MAP,
            default_next_question_key=self._ANY_DEFAULT_NEXT_QUESTION_KEY,
            default_from_toml={
                "toml_file": self._ANY_TOML_FILE,
                "env": {"key": self._ANY_EXTRA_CONTEXT_KEY},
                "cmd_names": self._ANY_COMMAND_NAMES,
                "section": self._ANY_SECTION,
                "key": self._ANY_KEY,
            },
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
        answer = self.question.ask()
        self.assertEqual(answer, self._ANY_ANSWER)
        mock_click.prompt.assert_called_once_with(text=self.question.text, default=self.question.default_answer)

    @patch("samcli.lib.cookiecutter.question.SamConfig")
    @patch("samcli.lib.cookiecutter.question.click")
    def test_ask_resolves_from_toml_when_toml_file_not_found(self, mock_click, mock_samconfig):
        # Setup
        toml_mock = Mock()
        mock_samconfig.return_value = toml_mock
        toml_mock.exists.return_value = False
        question = self.get_question_with_default_from_toml()

        # Trigger
        question.ask(extra_context={self._ANY_EXTRA_CONTEXT_KEY: self._ANY_EXTRA_CONTEXT_VALUE})

        # Verify
        toml_mock.exists.assert_called_once()
        # verify used the question's direct default value as there is no toml resolved value
        mock_click.prompt.assert_called_once_with(text=self.question.text, default=self.question.default_answer)

    @patch("samcli.lib.cookiecutter.question.SamConfig")
    @patch("samcli.lib.cookiecutter.question.click")
    def test_ask_resolves_from_toml_when_missing_required_toml_keys(self, mock_click, mock_samconfig):
        # Setup
        toml_mock = Mock()
        mock_samconfig.return_value = toml_mock
        toml_mock.exists.return_value = True
        question = self.get_question_with_default_from_toml()
        del question._default_from_toml["section"]

        # Trigger
        with self.assertRaises(KeyError):
            question.ask(extra_context={self._ANY_EXTRA_CONTEXT_KEY: self._ANY_EXTRA_CONTEXT_VALUE})

    @patch("samcli.lib.cookiecutter.question.SamConfig")
    @patch("samcli.lib.cookiecutter.question.click")
    def test_ask_resolves_from_toml_when_need_to_resolve_from_missing_extra_context(self, mock_click, mock_samconfig):
        # Setup
        toml_mock = Mock()
        mock_samconfig.return_value = toml_mock
        toml_mock.exists.return_value = True
        question = self.get_question_with_default_from_toml()

        # Trigger
        with self.assertRaises(KeyError):
            question.ask()  # the env key needs to resolve "key_from_extra_context" but no extra_context given

    @patch("samcli.lib.cookiecutter.question.SamConfig")
    @patch("samcli.lib.cookiecutter.question.click")
    def test_ask_resolves_from_toml_and_extra_context_when_required_key_attribute_is_missing(
        self, mock_click, mock_samconfig
    ):
        # Setup
        toml_mock = Mock()
        mock_samconfig.return_value = toml_mock
        toml_mock.exists.return_value = True
        question = self.get_question_with_default_from_toml()
        # let's remove the 'key' attribute
        del question._default_from_toml["env"]["key"]

        # Trigger
        with self.assertRaises(KeyError):
            question.ask()  # the env key needs to resolve "key_from_extra_context" but no extra_context given

    @patch("samcli.lib.cookiecutter.question.SamConfig")
    @patch("samcli.lib.cookiecutter.question.click")
    def test_ask_resolves_from_toml_when_need_to_resolve_from_missing_extra_context_key(
        self, mock_click, mock_samconfig
    ):
        # Setup
        toml_mock = Mock()
        mock_samconfig.return_value = toml_mock
        toml_mock.exists.return_value = True
        question = self.get_question_with_default_from_toml()

        # Trigger
        with self.assertRaises(KeyError):
            # the env key needs to resolve "key_from_extra_context" but extra_context_doesn't contain this key
            question.ask(extra_context={"not_key_from_extra_context": "not_value_from_extra_context"})

    @patch("samcli.lib.cookiecutter.question.SamConfig")
    @patch("samcli.lib.cookiecutter.question.click")
    def test_ask_resolves_from_toml_happy_case(self, mock_click, mock_samconfig):
        # Setup
        toml_mock = Mock()
        mock_samconfig.return_value = toml_mock
        toml_mock.exists.return_value = True
        toml_mock.get.return_value = self._ANY_TOML_ANSWER
        question = self.get_question_with_default_from_toml()

        # Trigger
        question.ask(extra_context={self._ANY_EXTRA_CONTEXT_KEY: self._ANY_EXTRA_CONTEXT_VALUE})

        # Verify
        mock_click.prompt.assert_called_once_with(text=self.question.text, default=self._ANY_TOML_ANSWER)
        toml_mock.get.assert_called_once_with(
            env=self._ANY_EXTRA_CONTEXT_VALUE,
            cmd_names=[self._ANY_COMMAND_NAMES],
            section=self._ANY_SECTION,
            key=self._ANY_KEY,
        )

    @patch.object(SamConfig, "get_all")
    @patch.object(SamConfig, "exists")
    @patch("samcli.lib.cookiecutter.question.click")
    def test_ask_resolves_from_toml_happy_case_when_optional_env_is_not_provided(
        self, mock_click, mock_samconfig_exists, mock_samconfig_get_all
    ):
        # Setup
        mock_samconfig_exists.return_value = True
        mock_samconfig_get_all.return_value = {self._ANY_KEY: self._ANY_TOML_ANSWER}
        question = self.get_question_with_default_from_toml()
        del question._default_from_toml["env"]  # remove the env

        # Trigger
        question.ask(extra_context={self._ANY_EXTRA_CONTEXT_KEY: self._ANY_EXTRA_CONTEXT_VALUE})

        # Verify
        mock_click.prompt.assert_called_once_with(text=self.question.text, default=self._ANY_TOML_ANSWER)
        mock_samconfig_get_all.assert_called_once_with(
            [self._ANY_COMMAND_NAMES],
            self._ANY_SECTION,
            DEFAULT_ENV,  # DEFAULT_ENV is used if no env is provided
        )


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
        answer = self.question.ask()
        self.assertEqual(answer, TestQuestion._ANY_OPTIONS[1])  # we deduct one from user's choice (base 1 vs base 0)
        mock_click.prompt.assert_called_once_with(
            text="Choice", default=self.question.default_answer, show_choices=False, type=ANY
        )
        mock_choice.assert_called_once_with(["1", "2", "3"])


class TestInfo(TestCase):
    @patch("samcli.lib.cookiecutter.question.click")
    def test_ask(self, mock_click):
        q = Info(text=TestQuestion._ANY_TEXT, key=TestQuestion._ANY_KEY)
        mock_click.echo.return_value = None
        answer = q.ask()
        self.assertIsNone(answer)
        mock_click.echo.assert_called_once_with(message=q.text)


class TestConfirm(TestCase):
    @patch("samcli.lib.cookiecutter.question.click")
    def test_ask(self, mock_click):
        q = Confirm(text=TestQuestion._ANY_TEXT, key=TestQuestion._ANY_KEY)
        mock_click.confirm.return_value = True
        answer = q.ask()
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
