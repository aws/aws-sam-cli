"""
Object to contain Lambda function pricing info.
This data gets stored in the graph, not a lambda function object
"""

class LambdaFunctionPricing:
    number_of_requests: int
    average_duration: int
    allocated_memory: float
    allocated_memory_unit: str

    def __init__(self):
        self.number_of_requests: int = None
        self.average_duration: int = None
        self.allocated_memory: float = None
        self.allocated_memory_unit: str = None
