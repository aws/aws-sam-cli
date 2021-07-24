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

    @property
    def number_of_requests(self) -> int:
        return self._number_of_requests

    @number_of_requests.setter
    def number_of_requests(self, num: int):
        self._number_of_requests = num

    @property
    def average_duration(self) -> int:
        return self._average_duration

    @average_duration.setter
    def average_duration(self, avg: int):
        self._average_duration = avg

    @property
    def allocated_memory(self) -> int:
        return self._allocated_memory

    @allocated_memory.setter
    def allocated_memory(self, mry: int):
        self._allocated_memory = mry

    @property
    def allocated_memory_unit(self) -> str:
        return self._allocated_memory_unit

    @allocated_memory_unit.setter
    def allocated_memory_unit(self, unit: str):
        self._allocated_memory_unit = unit

    @property
    def children(self) -> List:
        return self._children

    @children.setter
    def children(self, child_node: "LambdaFunction"):
        self._children.append(child_node)

    @property
    def parents(self) -> List:
        return self._parents

    @parents.setter
    def parents(self, parent_node: "LambdaFunction"):
        self._parents.append(parent_node)

    @property
    def tps(self) -> int:
        return self._tps

    @tps.setter
    def tps(self, tps: int):
        self._tps = tps

    @property
    def duration(self) -> int:
        return self._duration

    @duration.setter
    def duration(self, duration: int):
        self._duration = duration
