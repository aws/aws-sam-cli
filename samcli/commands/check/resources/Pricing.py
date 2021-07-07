import click

from click import confirm
from click import prompt


class Pricing:
    def __init__(self, graph):
        self.graph = graph

    def ask(self, question, min=1, max=float("inf")):
        valid_user_input = False
        user_input = None
        while valid_user_input is False:
            user_input = click.prompt(text=question, type=int)
            if user_input > max or user_input < min:
                click.echo("Please enter a number within the range")
            else:
                valid_user_input = True

        return user_input

    def ask_pricing_questions(self):
        asked_lambda_questions = False
        print("PRICING QUESTIONS")
        for resource in self.graph.get_resources_to_analyze():
            # Only ask lambda quetions once for all lambda functions
            if resource.get_resource_type() == "AWS::Lambda::Function" and asked_lambda_questions == False:
                asked_lambda_questions = True
                self.ask_lambda_function_questions(resource)

    def ask_lambda_function_questions(self, lambda_function):
        user_input_requests = self.ask(
            "What are the total number of requests expected from all lambda functions in a given month?",
            1,
            1000000000000000000000,
        )
        lambda_function.set_number_of_requests(user_input_requests)

        user_input_duration = self.ask("What is the expected average duration of all lambda functions?", 1, 900000)
        lambda_function.set_average_duration(user_input_duration)

        user_input_memory = self.ask(
            'Enter the amount of memory allocated, followed by a ":", followed by a valid unit of measurement [MB|GB]',
            1,
            10,
        )
