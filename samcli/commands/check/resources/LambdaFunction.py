"""
Class object for Lambda Functions. Contains object from template, as well as all data for lambda functions,
excluding pricing info
"""
from samcli.commands.check.resources.TemplateResource import TemplateResource


class LambdaFunction(TemplateResource):
    def __init__(self, resource_object, resource_type):
        super().__init__(resource_object, resource_type)
        self.duration = None
        self.tps = None
        self.parents = []
        self.children = []
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

    def add_child(self, child_node):
        self.children.append(child_node)

    def get_children(self):
        return self.children

    def add_parent(self, parent_node):
        self.parents.append(parent_node)

    def get_parents(self):
        return self.parents

    def set_tps(self, tps):
        self.tps = tps

    def get_tps(self):
        return self.tps

    def set_duration(self, duration):
        self.duration = duration

    def get_duration(self):
        return self.duration
