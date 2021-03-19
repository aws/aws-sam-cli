""" This module represents the questions to ask to the user to fulfill the cookiecutter context. """
from enum import Enum
from typing import Any, Dict, List, Optional, Type
import click


class QuestionKind(Enum):
    """ An Enum of possible question types. """

    info = "info"
    confirm = "confirm"
    choice = "choice"
    default = "default"


class Question:
    """
    A question to be prompt to the user in an interactive flow where the response is used to fulfill
    the cookiecutter context.

    Attributes
    ----------
    _key: str
        The key of the cookiecutter config to associate the answer with.
    _text: str
        The text to prompt to the user
    _required: bool
        Whether the user must provide an answer for this question or not.
    _default_answer: Optional[str]
        A default answer that is suggested to the user
    _next_question_map: Optional[Dict[str, str]]
        A simple branching mechanism, it refers to what is the next question to ask the user if he answered
        a particular answer to this question. this map is in the form of {answer: next-question-key}. this
        can be used in a flow like:
            supposed we are prompting the user for two resources r1 & r2 such that if the resource already
            exist then the user provide it otherwise we created it on his behave. the questions may look like:
                Question(key="r1" text="do you already have resource1?",
                         _next_question_map={"True": "r2", "False": "r1-creation"}
                Question(key="r1-creation" text="What do you like to name resource1?"}
                Question(key="r2" text="do you already have resource2?",
                         _next_question_map={"True": "r3", "False": "r2-creation"}
    _default_next_question_key: str
        The key of the next question that is not based on user's answer, i.e., if there is no matching in
        the _next_question_map
    """

    def __init__(
        self,
        key: str,
        text: str,
        default: Optional[str] = None,
        is_required: Optional[bool] = None,
        next_question_map: Optional[Dict[str, str]] = None,
        default_next_question_key: Optional[str] = None,
    ):
        self._key = key
        self._text = text
        self._required = is_required
        self._default_answer = default
        # if it is an optional question, set an empty default answer to prevent click from keep asking for an answer
        if not self._required and self._default_answer is None:
            self._default_answer = ""
        self._next_question_map: Dict[str, str] = next_question_map or {}
        self._default_next_question_key = default_next_question_key

    @property
    def key(self):
        return self._key

    @property
    def text(self):
        return self._text

    @property
    def default_answer(self):
        return self._default_answer

    @property
    def required(self):
        return self._required

    @property
    def next_question_map(self):
        return self._next_question_map

    @property
    def default_next_question_key(self):
        return self._default_next_question_key

    def ask(self) -> Any:
        return click.prompt(text=self._text, default=self._default_answer)

    def get_next_question_key(self, answer: Any) -> Optional[str]:
        # _next_question_map is a Dict[str(answer), str(next question key)]
        # so we need to parse the passed argument(answer) to str
        answer = str(answer)
        return self._next_question_map.get(answer, self._default_next_question_key)

    def set_default_next_question_key(self, next_question_key):
        self._default_next_question_key = next_question_key


class Info(Question):
    def ask(self) -> None:
        return click.echo(message=self._text)


class Confirm(Question):
    def ask(self) -> bool:
        return click.confirm(text=self._text)


class Choice(Question):
    def __init__(
        self,
        key: str,
        text: str,
        options: List[str],
        default: Optional[str] = None,
        is_required: Optional[bool] = None,
        next_question_map: Optional[Dict[str, str]] = None,
        default_next_question_key: Optional[str] = None,
    ):
        if not options:
            raise ValueError("No defined options")
        self._options = options
        super().__init__(key, text, default, is_required, next_question_map, default_next_question_key)

    def ask(self) -> str:
        click.echo(self._text)
        for index, option in enumerate(self._options):
            click.echo(f"\t{index + 1} - {option}")
        options_indexes = self._get_options_indexes(base=1)
        choices = list(map(str, options_indexes))
        choice = click.prompt(
            text="Choice",
            default=self._default_answer,
            show_choices=False,
            type=click.Choice(choices),
        )
        return self._options[int(choice) - 1]

    def _get_options_indexes(self, base: int = 0) -> List[int]:
        return list(range(base, len(self._options) + base))


class QuestionFactory:

    question_classes: Dict[QuestionKind, Type[Question]] = {
        QuestionKind.info: Info,
        QuestionKind.choice: Choice,
        QuestionKind.confirm: Confirm,
        QuestionKind.default: Question,
    }

    @staticmethod
    def create_question_from_json(question_json: Dict) -> Question:
        key = question_json["key"]
        text = question_json["question"]
        options = question_json.get("options")
        default = question_json.get("default")
        is_required = question_json.get("isRequired")
        next_question_map = question_json.get("nextQuestion")
        default_next_question = question_json.get("defaultNextQuestion")
        kind_str = question_json.get("kind")
        kind = QuestionKind(kind_str) if kind_str else QuestionKind.choice if options else QuestionKind.default

        klass = QuestionFactory.question_classes[kind]
        args = {
            "key": key,
            "text": text,
            "default": default,
            "is_required": is_required,
            "next_question_map": next_question_map,
            "default_next_question_key": default_next_question,
        }
        if klass == Choice:
            args["options"] = options

        return klass(**args)
