"""
A super class for all sub pricing classes. When a new resource is added and pricing
is implemebted for it, all common methods between resoruces will be implemented here
"""


class UniquePricingInfo:
    """
    Note: Currently, pricing is only implemented for lambda functions. Until pricing
    is implemeted for more resources, this class will not be utilized., since everything
    implemeted for lambda functions is currently unique to lambda functions.
    """

    def __init__(self):
        pass
