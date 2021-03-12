"""A flow of questions to be asked to the user in an interactive way."""
from typing import Any, Dict, Optional
import click
from .question import Question


class InteractiveFlow:
    """
    This class depends on the click module to prompt the user for answers to the questions of the flow.

    Attributes
    ----------
    _questions: Dict[str, Question]
        The questions to prompt the user for its answers
    _first_question_key: str
        The entry-point of the flow, it tells which question to ask the user first
    """

    def __init__(self, questions: Dict[str, Question], first_question_key: str):
        self._questions: Dict[str, Question] = questions
        self._first_question_key: str = first_question_key
        self._current_question: Optional[Question] = None

    @staticmethod
    def _ask_a_question(question: Question) -> Any:
        return click.prompt(text=question.text, default=question.default_answer)

    @staticmethod
    def _ask_a_yes_no_question(question: Question) -> bool:
        return click.confirm(text=question.text, default=question.default_answer)

    @staticmethod
    def _ask_a_multiple_choice_question(question: Question) -> Any:
        click.echo(question.text)
        for index, option in enumerate(question.options):
            click.echo(f"\t{index + 1} - {option}")
        choice = click.prompt(
            text="Choice",
            default=question.default_answer,
            show_choices=False,
            type=click.Choice(question.get_choices_indexes(base=1)),
        )
        return question.get_option(int(choice) - 1)

    def get_next_question(self, current_answer: Optional[str] = None) -> Optional[Question]:
        """
        Based on the answer of the current question, what is the next question to ask.

        Parameters
        ----------
        current_answer: str
            User's answer of the current question. This can be None of this is the first question or an optional
            question and the user didn't provide an answer to

        Returns: The next question defined in current question's next-question map or the first question if this
                is the start of the flow.
        """
        if not self._current_question:
            self._current_question = self._questions.get(self._first_question_key)
        else:
            next_question_key = self._current_question.get_next_question_key(current_answer)
            self._current_question = self._questions.get(next_question_key) if next_question_key else None
        return self._current_question

    def run(self, context: Dict) -> Dict:
        """
        starts the flow, collects user's answers to the question and return a new copy of the passed context
        with the answers appended to the copy

        Parameters
        ----------
        context: Dict
            The cookiecutter context before prompting this flow's questions

        Returns: A new copy of the context with user's answers added to the copy such that each answer is
                 associated to the key of the corresponding question
        """
        context = context.copy()
        question = self.get_next_question()
        answer: Any = None
        while question:
            if question.is_info():
                click.echo(question.text)
            elif question.is_mcq():
                answer = InteractiveFlow._ask_a_multiple_choice_question(question)
            elif question.is_yes_no():
                answer = InteractiveFlow._ask_a_yes_no_question(question)
            else:
                answer = InteractiveFlow._ask_a_question(question)
            context[question.key] = answer
            question = self.get_next_question(answer)
        return context
