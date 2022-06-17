"""
Interface for Consumers
"""
import abc
from typing import Generic, TypeVar

T = TypeVar("T")


class Consumer(Generic[T]):
    @abc.abstractmethod
    def consume(self, data: T):
        pass
