from abc import abstractmethod


class PricingCalculations:
    def __init__(self, graph):
        self.graph = graph

    @abstractmethod
    def run_calculations(self):
        pass

    @abstractmethod
    def get_charge_and_request_amounts(self):
        pass

    @abstractmethod
    def get_aws_pricing_info(self, region):
        pass

    @abstractmethod
    def determine_cost(self):
        pass
