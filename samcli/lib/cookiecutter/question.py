"""This module represents the questions to ask to the user to fulfill the cookiecutter context."""

from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Dict, List, Optional, Type, Union

import click


class QuestionKind(Enum):
    """An Enum of possible question types."""

    info = "info"
    confirm = "confirm"
    choice = "choice"
    question = "question"


class Promptable(ABC):
    """
    Abstract class Question, Info, Choice, Confirm implement.
    These classes need to implement their own prompt() method to prompt differently.
    """

    @abstractmethod
    def prompt(self, text: str, default_answer: Optional[Any]) -> Any:
        pass


class Question(Promptable):
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
    _default_answer: Optional[Union[str, Dict]]
        A default answer that is suggested to the user,
        it can be directly provided (a string)
        or resolved from cookiecutter context (a Dict, in the form of {"keyPath": [...,]})
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
        default: Optional[Union[str, Dict]] = None,
        is_required: Optional[bool] = None,
        allow_autofill: Optional[bool] = None,
        next_question_map: Optional[Dict[str, str]] = None,
        default_next_question_key: Optional[str] = None,
    ):
        self._key = key
        self._text = text
        self._required = is_required
        self._allow_autofill = allow_autofill
        self._default_answer = default
        # if it is an optional question, set an empty default answer to prevent click from keep asking for an answer
        if not self._required and self._default_answer is None:
            self._default_answer = ""
        self._next_question_map: Dict[str, str] = next_question_map or {}
        self._default_next_question_key = default_next_question_key

    @property
    def key(self) -> str:
        return self._key

    @property
    def text(self) -> str:
        return self._text

    @property
    def default_answer(self) -> Optional[Any]:
        return self._resolve_default_answer()

    @property
    def required(self) -> Optional[bool]:
        return self._required

    @property
    def next_question_map(self) -> Dict[str, str]:
        return self._next_question_map

    @property
    def default_next_question_key(self) -> Optional[str]:
        return self._default_next_question_key

    def ask(self, context: Optional[Dict] = None) -> Any:
        """
        prompt the user this question

        Parameters
        ----------
        context
            The cookiecutter context dictionary containing previous questions' answers and default values

        Returns
        -------
        The user provided answer.
        """
        resolved_default_answer = self._resolve_default_answer(context)

        # skip the question and directly use the default value if autofill is allowed.
        if resolved_default_answer is not None and self._allow_autofill:
            return resolved_default_answer

        # if it is an optional question with no default answer,
        # set an empty default answer to prevent click from keep asking for an answer
        if not self._required and resolved_default_answer is None:
            resolved_default_answer = ""

        return self.prompt(self._resolve_text(context), resolved_default_answer)

    def prompt(self, text: str, default_answer: Optional[Any]) -> Any:
        return click.prompt(text=text, default=default_answer)

    def get_next_question_key(self, answer: Any) -> Optional[str]:
        # _next_question_map is a Dict[str(answer), str(next question key)]
        # so we need to parse the passed argument(answer) to str
        answer = str(answer)
        return self._next_question_map.get(answer, self._default_next_question_key)

    def set_default_next_question_key(self, next_question_key: str) -> None:
        self._default_next_question_key = next_question_key

    def _resolve_key_path(self, key_path: List, context: Dict) -> List[str]:
        """
        key_path element is a list of str and Dict.
        When the element is a dict, in the form of { "valueOf": question_key },
        it means it refers to the answer to another questions.
        _resolve_key_path() will replace such dict with the actual question answer

        Parameters
        ----------
        key_path
            The key_path list containing str and dict
        context
            The cookiecutter context containing answers to previous answered questions
        Returns
        -------
            The key_path list containing only str
        """
        resolved_key_path: List[str] = []
        for unresolved_key in key_path:
            if isinstance(unresolved_key, str):
                resolved_key_path.append(unresolved_key)
            elif isinstance(unresolved_key, dict):
                if "valueOf" not in unresolved_key:
                    raise KeyError(f'Missing key "valueOf" in question default keyPath element "{unresolved_key}".')
                query_question_key: str = unresolved_key.get("valueOf", "")
                if query_question_key not in context:
                    raise KeyError(
                        f'Invalid question key "{query_question_key}" referenced '
                        f"in default answer of question {self.key}"
                    )
                resolved_key_path.append(context[query_question_key])
            else:
                raise ValueError(f'Invalid value "{unresolved_key}" in key path')
        return resolved_key_path

    def _resolve_value_from_expression(self, expression: Any, context: Optional[Dict] = None) -> Optional[Any]:
        """
        a question may have a value provided directly as string or number value
        or indirectly from cookiecutter context using a key path

        Parameters
        ----------
        context
            Cookiecutter context used to resolve values.

        Raises
        ------
        KeyError
            When an expression depends on the answer to a non-existent question
        ValueError
            The expression is malformed

        Returns
        -------
        Optional value, it might be resolved from cookiecutter context using specified key path.

        """
        if isinstance(expression, dict):
            context = context if context else {}

            # load value using key path from cookiecutter
            if "keyPath" not in expression:
                raise KeyError(f'Missing key "keyPath" in "{expression}".')
            unresolved_key_path = expression.get("keyPath", [])
            if not isinstance(unresolved_key_path, list):
                raise ValueError(f'Invalid expression "{expression}" in question {self.key}')

            return context.get(str(self._resolve_key_path(unresolved_key_path, context)))
        return expression

    def _resolve_text(self, context: Optional[Dict] = None) -> str:
        resolved_text = self._resolve_value_from_expression(self._text, context)
        if resolved_text is None:
            raise ValueError(f"Cannot resolve value from expression: {self._text}")
        return str(resolved_text)

    def _resolve_default_answer(self, context: Optional[Dict] = None) -> Optional[Any]:
        return self._resolve_value_from_expression(self._default_answer, context)


class Info(Question):
    def prompt(self, text: str, default_answer: Optional[Any]) -> Any:
        return click.echo(message=text)


class Confirm(Question):
    def prompt(self, text: str, default_answer: Optional[Any]) -> Any:
        return click.confirm(text=text)


class Choice(Question):
    def __init__(
        self,
        key: str,
        text: str,
        options: List[str],
        default: Optional[str] = None,
        is_required: Optional[bool] = None,
        allow_autofill: Optional[bool] = None,
        next_question_map: Optional[Dict[str, str]] = None,
        default_next_question_key: Optional[str] = None,
    ):
        if not options:
            raise ValueError("No defined options")
        self._options = options
        super().__init__(key, text, default, is_required, allow_autofill, next_question_map, default_next_question_key)

    def prompt(self, text: str, default_answer: Optional[Any]) -> Any:
        click.echo(text)
        for index, option in enumerate(self._options):
            click.echo(f"\t{index + 1} - {option}")
        options_indexes = self._get_options_indexes(base=1)
        choices = list(map(str, options_indexes))
        choice = click.prompt(
            text="Choice",
            default=default_answer,
            show_choices=False,
            type=click.Choice(choices),
            show_default=default_answer is not None,
        )
        return self._options[int(choice) - 1]

    def _get_options_indexes(self, base: int = 0) -> List[int]:
        return list(range(base, len(self._options) + base))


class QuestionFactory:
    question_classes: Dict[QuestionKind, Type[Question]] = {
        QuestionKind.info: Info,
        QuestionKind.choice: Choice,
        QuestionKind.confirm: Confirm,
        QuestionKind.question: Question,
    }

    @staticmethod
    def create_question_from_json(question_json: Dict) -> Question:
        key = question_json["key"]
        text = question_json["question"]
        options = question_json.get("options")
        default = question_json.get("default")
        is_required = question_json.get("isRequired")
        allow_autofill = question_json.get("allowAutofill")
        next_question_map = question_json.get("nextQuestion")
        default_next_question = question_json.get("defaultNextQuestion")
        kind_str = question_json.get("kind")
        kind = QuestionKind(kind_str) if kind_str else QuestionKind.choice if options else QuestionKind.question

        klass = QuestionFactory.question_classes[kind]
        args = {
            "key": key,
            "text": text,
            "default": default,
            "is_required": is_required,
            "allow_autofill": allow_autofill,
            "next_question_map": next_question_map,
            "default_next_question_key": default_next_question,
        }
        if klass == Choice:
            args["options"] = options

        return klass(**args)
