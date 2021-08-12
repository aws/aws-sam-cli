"""
A super class for all sub pricing classes. When a new resource is added and pricing
is implemented for it, all common methods between resoruces will be implemented here
"""
from abc import abstractmethod


class UniquePricingInfo:
    def __init__(self):
        pass

    @abstractmethod
    def ask_questions(self):
        """
        Asks the pricing questions, depending on what resource is being accessed.
        """
