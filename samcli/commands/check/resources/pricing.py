"""
Pricing questions are asked here. Pricing is only done for
Lambda Functions as of now. Data is stored in graph in
Lambda function pricing object.
"""

from typing import List, Tuple
import click

from samcli.commands.check.resources.graph import Graph
from samcli.commands.check.resources.lambda_function_pricing import LambdaFunctionPricing
from samcli.commands._utils.resources import AWS_LAMBDA_FUNCTION


class Pricing:
    _graph: Graph
    _max_num_requests: int
    _min_memory_amount: int
    _max_memory_amount: int
    _max_duration: int

    def __init__(self, graph: Graph) -> None:
        """
        Args:
            graph (Graph): The graph object. This is where all of the data is stored
        """
        self._graph: Graph = graph
        self._max_num_requests: int = 1000000000000000000000
        self._min_memory_amount: int = 128
        self._max_memory_amount: int = 10000
        self._max_duration: int = 900000
        self.asked_lambda_questions = False

    def ask_pricing_questions(self, resource) -> None:
        """
        Pricing quetions for various resources get asked here
        Pricing is only done for Lambda functions now
        """
        if resource.resource_type == AWS_LAMBDA_FUNCTION and self.asked_lambda_questions == False:
            click.echo("Pricing Questions")
            self.asked_lambda_questions = True
            self._ask_lambda_function_questions()

    def _ask_lambda_function_questions(self) -> None:
        """Lambda function pricing questions"""

        lambda_funciton_pricing = LambdaFunctionPricing()
        user_input_requests = _ask(
            "What are the total number of requests expected from all lambda functions in a given month?",
            1,
            self._max_num_requests,
        )
        lambda_funciton_pricing.number_of_requests = user_input_requests

        user_input_duration = _ask(
            "What is the expected average duration of all lambda functions (ms)?", 1, self._max_duration
        )
        lambda_funciton_pricing.average_duration = user_input_duration

        user_input_memory, user_input_unit = self._ask_memory(
            'Enter the amount of memory allocated (128MB - 10GB), followed by a ":", '
            "followed by a valid unit of measurement [MB|GB]"
        )
        lambda_funciton_pricing.allocated_memory = user_input_memory
        lambda_funciton_pricing.allocated_memory_unit = user_input_unit

        self._graph.lambda_function_pricing_info = lambda_funciton_pricing

    def _correct_memory_input(self, user_input_split: List) -> bool:
        """Checks if user input correct memory amount and unit

        Args:
            user_input_split (List): User enterd data [memory_amount, memory_unit]

        Returns:
            [type]: [description]
        """
        if len(user_input_split) != 2:
            click.echo("Please enter a valid input.")
            return False

        memory_amount = user_input_split[0]
        memory_unit = user_input_split[1]
        valid_units = ["MB", "GB"]

        try:
            float(memory_amount)
        except ValueError:  # Not a valid number
            click.echo("Please enter a valid amount of memory.")
            return False

        if memory_unit not in valid_units:
            click.echo("Please enter a valid memory unit.")
            return False

        # At this point, memory_amount and memory_unit are both valid inputs. Now test if memory_amount is within range

        memory_amount_float = float(memory_amount)

        if memory_unit == "GB":
            # Convert to MB for testing range
            memory_amount_float *= 1000

        if (
            memory_amount_float < self._min_memory_amount or memory_amount_float > self._max_memory_amount
        ):  # units are in MB
            click.echo("Please enter a valid amount of memory within the range.")
            return False

        return True

    def _ask_memory(self, question: str) -> Tuple[float, str]:
        """Ask user memory pricing question for lambda functions

        Args:
            question (str): The question to ask the user

        Returns:
            str: memory amount and unit
        """
        valid_user_input = False
        user_input_split = []
        while not valid_user_input:
            user_input = click.prompt(text=question, type=str)
            user_input_split = user_input.split(":")
            if self._correct_memory_input(user_input_split):
                valid_user_input = True

        return user_input_split[0], user_input_split[1]


def _ask(question: str, min_val: int = 1, max_val: float = float("inf")) -> int:
    """Prompts the user with a question for some input. A min and max value
    are passed and used.

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
