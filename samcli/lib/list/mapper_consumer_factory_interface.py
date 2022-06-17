"""
Interface for MapperConsumerFactory
"""
import abc


class MapperConsumerFactoryInterface:
    @abc.abstractmethod
    def create(self, producer, output):
        pass
