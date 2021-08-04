"""
Class for graph. All data is stored in the graph directly, or within nodes that are stored in the graph
"""
from typing import List, Optional, Union

from samcli.commands.check.resources.lambda_function_pricing import LambdaFunctionPricing
from samcli.commands.check.resources.lambda_function import LambdaFunction
from samcli.commands.check.resources.warning import CheckWarning


class CheckGraph:
    """
    A graph object stores four main item types.

    entry_points: All possible entry points to the application based on the template.
    resources_to_analyze: All resources that need to be directly checked for bottle
      neck issues (just lambda functions for now).
    green/yellow/red/red_burst_warnings: The four different warning types that
      the user can be presented
    lambda_function_pricing_info: Contains the user entered data for the lambda
      pricing questions
    """

    entry_points: List[Union[LambdaFunction]]
    resources_to_analyze: List[Union[LambdaFunction]]
    green_warnings: List[CheckWarning]
    yellow_warnings: List[CheckWarning]
    red_warnings: List[CheckWarning]
    red_burst_warnings: List[CheckWarning]
    lambda_function_pricing_info: Optional[LambdaFunctionPricing]

    def __init__(self, lambda_functions: List):
        self.entry_points: List[Union[LambdaFunction]] = []
        self.resources_to_analyze: List[Union[LambdaFunction]] = []
        self.green_warnings: List[CheckWarning] = []
        self.yellow_warnings: List[CheckWarning] = []
        self.red_warnings: List[CheckWarning] = []
        self.red_burst_warnings: List[CheckWarning] = []
        self.lambda_function_pricing_info: Optional[LambdaFunctionPricing] = None

        self._generate(lambda_functions)

    def _generate(self, lambda_functions: List) -> None:
        """Generates the graph based on the connections calulated
        Parameters
        ----------
            lambda_functions: List
              List of all lambda functions in template
        """
        # Find all entry points
        for function in lambda_functions:
            if not function.parents:  # No parent resourecs, so this is an entry point
                self.entry_points.append(function)
