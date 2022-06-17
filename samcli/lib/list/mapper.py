"""
Interface for Mappers
"""
import abc
from typing import Generic, TypeVar

T = TypeVar("T")


class Mapper(Generic[T]):
    @abc.abstractmethod
    def map(self, data: T):
        pass
