""" This module represents the questions to ask to the user to fulfill the cookiecutter context. """
from enum import Enum
from typing import Any, Dict, List, Optional


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
    _options: Optional[List[str]]
        if this is a mcq question, this attribute specifies the possible choices
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
    _kind: QuestionKind
        the kind of the question, it can be one of the values of the QuestionKind enum. This basically directs
        click on how to prompt the user for the answer; click.prompt, click.confirm, click.choice ...etc
    """

    def __init__(
        self,
        key: str,
        text: str,
        options: Optional[List[str]] = None,
        default: Optional[str] = None,
        is_required: Optional[bool] = False,
        next_question_map: Optional[Dict[str, str]] = None,
        kind: Optional[QuestionKind] = None,
    ):
        self._key = key
        self._text = text
        self._options = options or []
        self._required = is_required
        self._default_answer = default
        # if it is an optional question, set an empty default answer to prevent click from keep asking for an answer
        if not self._required and self._default_answer is None:
            self._default_answer = ""
        self._next_question_map = next_question_map or {}
        self._kind = kind or (QuestionKind.confirm if options else QuestionKind.default)

    @property
    def key(self):
        return self._key

    @property
    def text(self):
        return self._text

    @property
    def options(self):
        return self._options

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
    def kind(self):
        return self._kind

    def get_choices_indexes(self, base: int = 0) -> List[str]:
        if self._options:
            choices = list(range(base, len(self._options) + base))
            return list(map(str, choices))
        return list()

    def get_option(self, index) -> Any:
        return self._options[index]

    def is_mcq(self) -> bool:
        return len(self._options) > 0

    def is_yes_no(self) -> bool:
        return self._kind == QuestionKind.confirm

    def is_info(self) -> bool:
        return self._kind == QuestionKind.info

    def get_next_question_key(self, answer) -> Optional[str]:
        answer = str(answer)
        return self._next_question_map.get(answer, self.get_default_next_question_key())

    def get_default_next_question_key(self) -> Optional[str]:
        return self._next_question_map.get("*")

    def set_next_question_key(self, answer, next_question_key):
        self._next_question_map[answer] = next_question_key

    def set_default_next_question_key(self, next_question_key):
        self.set_next_question_key("*", next_question_key)
