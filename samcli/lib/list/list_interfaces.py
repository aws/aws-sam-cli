"""
Interface for MapperConsumerFactory, Producer, Mapper, ListInfoPullerConsumer
"""
from abc import ABC, abstractmethod
from enum import Enum
from typing import Generic, TypeVar

InputType = TypeVar("InputType")
OutputType = TypeVar("OutputType")


class ListInfoPullerConsumer(ABC, Generic[InputType]):
    """
    Interface definition to consume and display data
    """

    @abstractmethod
    def consume(self, data: InputType):
        """
        Parameters
        ----------
        data: TypeVar
            Data for the consumer to print
        """


class Mapper(ABC, Generic[InputType, OutputType]):
    """
    Interface definition to map data to json or table
    """

    @abstractmethod
    def map(self, data: InputType) -> OutputType:
        """
        Parameters
        ----------
        data: TypeVar
            Data for the mapper to map

        Returns
        -------
        Any
            Mapped output given the data
        """


class Producer(ABC):
    """
    Interface definition to produce data for the mappers and consumers
    """

    mapper: Mapper
    consumer: ListInfoPullerConsumer

    @abstractmethod
    def produce(self):
        """
        Produces the data for the mappers and consumers
        """


class MapperConsumerFactoryInterface(ABC):
    """
    Interface definition to create mapper-consumer factories
    """

    @abstractmethod
    def create(self, producer, output):
        """
        Parameters
        ----------
        producer: str
            A string indicating which producer is calling the function
        output: str
            A string indicating the output type

        Returns
        -------
        MapperConsumerContainer
            A container that contains a mapper and a consumer
        """


class ProducersEnum(Enum):
    STACK_OUTPUTS_PRODUCER = 1
    RESOURCES_PRODUCER = 2
    ENDPOINTS_PRODUCER = 3
