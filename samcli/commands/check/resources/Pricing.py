import click

from .LambdaFunctionPricing import LambdaFunctionPricing


class Pricing:
    def __init__(self, graph):
        self.graph = graph
        self.asked_lambda_questions = False

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

    def ask_memory(self, question, min=1, max=float("inf")):
        valid_user_input = False
        user_input_split = None
        while valid_user_input is False:
            user_input = click.prompt(text=question, type=str)
            user_input_split = user_input.split(":")
            if self.correct_memory_input(user_input_split):
                valid_user_input = True

        return user_input_split[0], user_input_split[1]

    def correct_memory_input(self, user_input_split):
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

        if memory_amount_float < 128 or memory_amount_float > 10000:  # units are in MB
            click.echo("Please enter a valid amount of memory within the range.")
            return False

        return True

    def ask_pricing_question(self, resource):
        print("PRICING QUESTIONS")
        if resource.get_resource_type() == "AWS::Lambda::Function" and self.asked_lambda_questions == False:
            self.asked_lambda_questions = True
            self.ask_lambda_function_questions(resource)

    def ask_lambda_function_questions(self, lambda_function):
        lambda_funciton_pricing = LambdaFunctionPricing()
        user_input_requests = self.ask(
            "What are the total number of requests expected from all lambda functions in a given month?",
            1,
            1000000000000000000000,
        )
        lambda_funciton_pricing.set_number_of_requests(user_input_requests)

        user_input_duration = self.ask("What is the expected average duration of all lambda functions (ms)?", 1, 900000)
        lambda_funciton_pricing.set_average_duration(user_input_duration)

        user_input_memory, user_input_unit = self.ask_memory(
            'Enter the amount of memory allocated (128MB - 10GB), followed by a ":", followed by a valid unit of measurement [MB|GB]',
            1,
            10,
        )
        lambda_funciton_pricing.set_allocated_memory(user_input_memory)
        lambda_funciton_pricing.set_allocated_memory_unit(user_input_unit)

        self.graph.set_lambda_function_pricing_info(lambda_funciton_pricing)
