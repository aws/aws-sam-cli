"""Hooks abstract classes"""
from abc import ABC, abstractmethod


class Hooks(ABC):
    @abstractmethod
    def prepare(self, params: dict) -> dict:
        pass
