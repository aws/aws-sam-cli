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
        self._duration = -1
        self._tps = -1
        self._parents: List = []
        self._children: List = []
        self._number_of_requests = -1
        self._average_duration = -1
        self._allocated_memory = -1
        self._allocated_memory_unit = ""

    def set_number_of_requests(self, num: int):
        self._number_of_requests = num

    def get_number_of_requests(self) -> int:
        return self._number_of_requests

    def set_average_duration(self, avg: int):
        self._average_duration = avg

    def get_average_duration(self) -> int:
        return self._average_duration

    def set_allocated_memory(self, mry: int):
        self._allocated_memory = mry

    def get_allocated_memory(self) -> int:
        return self._allocated_memory

    def set_allocated_memory_unit(self, unit: str):
        self._allocated_memory_unit = unit

    def get_allocated_memory_unit(self) -> str:
        return self._allocated_memory_unit

    def add_child(self, child_node: "LambdaFunction"):
        self._children.append(child_node)

    def get_children(self) -> List:
        return self._children

    def add_parent(self, parent_node: "LambdaFunction"):
        self._parents.append(parent_node)

    def get_parents(self) -> List:
        return self._parents

    def set_tps(self, tps: int):
        self._tps = tps

    def get_tps(self) -> int:
        return self._tps

    def set_duration(self, duration: int):
        self._duration = duration

    def get_duration(self) -> int:
        return self._duration

    # Property objects
    duration = property(get_duration, set_duration)
    tps = property(get_tps, set_tps)
    parents = property(get_parents, add_parent)
    children = property(get_children, add_child)
