"""
A utility method used to ask the user a question. An int is returned only
if it is within the specified range.
"""

import click


def ask(question: str, min_val: int = 1, max_val: float = float("inf")) -> int:
    """Prompts the user with a question for some input. A min and max value
    can be passed and used.

    Args:
        question (str): The question to ask the user
        min_val (int, optional): The min value the user can enter. Defaults to 1.
        max_val (float, optional): The max value the user can enter. Defaults to float("inf").

    Returns:
        [type]: [description]
    """
    valid_user_input = False
    user_input = -1
    while not valid_user_input:
        user_input = click.prompt(text=question, type=int)
        if user_input < min_val or user_input > max_val:
            click.echo("Please enter a number within the range")
        else:
            valid_user_input = True

    return user_input
