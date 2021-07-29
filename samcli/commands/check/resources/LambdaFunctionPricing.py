class LambdaFunctionPricing:
    def __init__(self):
        self.number_of_requests = None
        self.average_duration = None
        self.allocated_memory = None
        self.allocated_memory_unit = None

    def set_number_of_requests(self, num):
        self.number_of_requests = num

    def get_number_of_requests(self):
        return self.number_of_requests

    def set_average_duration(self, avg):
        self.average_duration = avg

    def get_average_duration(self):
        return self.average_duration

    def set_allocated_memory(self, mry):
        self.allocated_memory = mry

    def get_allocated_memory(self):
        return self.allocated_memory

    def set_allocated_memory_unit(self, unit):
        self.allocated_memory_unit = unit

    def get_allocated_memory_unit(self):
        return self.allocated_memory_unit
