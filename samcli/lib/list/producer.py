"""
Interface for Producers
"""
import abc

from samcli.lib.list.consumer import Consumer
from samcli.lib.list.mapper import Mapper


class Producer:
    mapper: Mapper
    consumer: Consumer

    @abc.abstractmethod
    def produce(self):
        pass
