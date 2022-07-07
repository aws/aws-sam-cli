"""Hooks abstract classes"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, Optional


@dataclass
class PrepareParams:
    OutputDirPath: str
    Debug: bool
    Profile: Optional[str]
    Region: Optional[str]


class Hooks(ABC):
    @abstractmethod
    def prepare(self, params: PrepareParams) -> dict:
        pass


@dataclass
class IacPrepareParams(PrepareParams):
    IacProjectPath: str


@dataclass
class IacApplicationInfo:
    metadata_file: str


@dataclass
class IacPrepareOutput:
    iac_applications: Dict[str, IacApplicationInfo]


class IacHooks(Hooks):
    @abstractmethod
    def prepare(self, params: IacPrepareParams) -> IacPrepareOutput:
        pass
