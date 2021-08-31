"""A flow of questions to be asked to the user in an interactive way."""
from typing import Any, Dict, Optional, List, Tuple

import click

from .question import Question
from ..utils.colors import Colored


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
        self._color = Colored()

    def advance_to_next_question(self, current_answer: Optional[Any] = None) -> Optional[Question]:
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

    def run(
        self,
        context: Dict,
    ) -> Dict:
        """
        starts the flow, collects user's answers to the question and return a new copy of the passed context
        with the answers appended to the copy

        Parameters
        ----------
        context: Dict
            The cookiecutter context before prompting this flow's questions
            The context can be used to provide default values, and support both str keys and List[str] keys.

        Returns
        -------
        A new copy of the context with user's answers added to the copy such that each answer is
             associated to the key of the corresponding question
        """
        context = context.copy()
        answers: List[Tuple[str, Any]] = []

        question = self.advance_to_next_question()
        while question:
            answer = question.ask(context=context)
            context[question.key] = answer
            answers.append((question.key, answer))
            question = self.advance_to_next_question(answer)

        # print summary
        click.echo(self._color.bold("SUMMARY"))
        click.echo("We will generate a pipeline config file based on the following information:")

        for question_key, answer in answers:
            if answer is None:
                # ignore unanswered questions
                continue

            question = self._questions[question_key]
            click.echo(f"\t{question.text}: {self._color.underline(str(answer))}")

        return context
