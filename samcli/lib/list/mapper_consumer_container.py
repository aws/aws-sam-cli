"""
Container for a mapper and a consumer
"""
from dataclasses import dataclass

from samcli.lib.list.list_interfaces import ListInfoPullerConsumer, Mapper


@dataclass
class MapperConsumerContainer:
    mapper: Mapper
    consumer: ListInfoPullerConsumer
