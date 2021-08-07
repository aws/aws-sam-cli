"""
Class for graph. All data is stored in the graph directly, or within nodes that are stored in the graph
"""
from typing import Dict, List, Union

from samcli.commands.check.resources.lambda_function import LambdaFunction
from samcli.commands.check.resources.warning import CheckWarning
from samcli.commands.check.resources.unique_pricing_info import UniquePricingInfo


class CheckGraph:
    """
    A graph object stores four main item types.

    entry_points: All possible entry points to the application based on the template.
    resources_to_analyze: All resources that need to be directly checked for bottle
      neck issues (just lambda functions for now).
    green/yellow/red/red_burst_warnings: The four different warning types that
      the user can be presented
    unique_pricing_info: Contains the user entered data for all pricing questions
      for every resource
    """

    entry_points: List[Union[LambdaFunction]]
    resources_to_analyze: List[Union[LambdaFunction]]
    green_warnings: List[CheckWarning]
    yellow_warnings: List[CheckWarning]
    red_warnings: List[CheckWarning]
    red_burst_warnings: List[CheckWarning]
    unique_pricing_info: Dict[str, UniquePricingInfo]

    def __init__(self, lambda_functions: List[LambdaFunction]):
        self.entry_points = []
        self.resources_to_analyze = {}
        self.green_warnings = []
        self.yellow_warnings = []
        self.red_warnings = []
        self.red_burst_warnings = []
        self.unique_pricing_info = {}

        self._generate(lambda_functions)

    def _generate(self, lambda_functions: List[LambdaFunction]) -> None:
        """Generates the graph based on the connections calulated
        Parameters
        ----------
            lambda_functions: List[LambdaFunction]
              List of all lambda functions in template
        """
        # Find all entry points
        for function in lambda_functions:
            if not function.parents:  # No parent resourecs, so this is an entry point
                self.entry_points.append(function)
