"""
Superclass for pricing calculations. Each resource will inherit
this class and implement necessary methods to determine pricing
cost of the given resource
"""

from abc import abstractmethod


class PricingCalculations:
    def __init__(self, graph):
        self._graph = graph

    @abstractmethod
    def run_calculations(self):
        """
        Runs the methods to get the information to calcualte the costs,
        and then calcualtes the cost
        """

    @abstractmethod
    def _get_charge_and_request_amounts(self):
        """
        Gets the price per use (might be a different unit depending on
        the resource) and the maximum allowed uses (again, might be a
        different unit of mreasurement) for the given resource
        """

    @abstractmethod
    def _get_aws_pricing_info(self, region: str):
        """
        Gets the json file from the API based on the region and resource type

        Parameters
        ----------
            region: str
                The region for determining what pricing info to get
        """

    @abstractmethod
    def _determine_cost(self):
        """
        Uses the retrieved data from the api and the user enterd data to determine
        the cost of the given resource
        """
