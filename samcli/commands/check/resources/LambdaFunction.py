"""
Class object for Lambda Functions. Contains object from template, as well as all data for lambda functions,
excluding pricing info
"""
from typing import List
from samcli.lib.providers.provider import Function
from samcli.commands.check.resources.TemplateResource import TemplateResource


class LambdaFunction(TemplateResource):
    def __init__(self, resource_object: Function, resource_type: str):
        super().__init__(resource_object, resource_type)
        self.duration = 0
        self.tps = 0
        self.parents: List = []
        self.children: List = []
        self.number_of_requests = 0
        self.average_duration = 0
        self.allocated_memory = 0
        self.allocated_memory_unit = ""

    def set_number_of_requests(self, num: int):
        self.number_of_requests = num

    def get_number_of_requests(self) -> int:
        return self.number_of_requests

    def set_average_duration(self, avg: int):
        self.average_duration = avg

    def get_average_duration(self) -> int:
        return self.average_duration

    def set_allocated_memory(self, mry: int):
        self.allocated_memory = mry

    def get_allocated_memory(self) -> int:
        return self.allocated_memory

    def set_allocated_memory_unit(self, unit: str):
        self.allocated_memory_unit = unit

    def get_allocated_memory_unit(self) -> str:
        return self.allocated_memory_unit

    def add_child(self, child_node: "LambdaFunction"):
        self.children.append(child_node)

    def get_children(self) -> List:
        return self.children

    def add_parent(self, parent_node: "LambdaFunction"):
        self.parents.append(parent_node)

    def get_parents(self) -> List:
        return self.parents

    def set_tps(self, tps: int):
        self.tps = tps

    def get_tps(self) -> int:
        return self.tps

    def set_duration(self, duration: int):
        self.duration = duration

    def get_duration(self) -> int:
        return self.duration
