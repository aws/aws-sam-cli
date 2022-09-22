from enum import Enum


class ContainersInitializationMode(Enum):
    EAGER = "EAGER"
    LAZY = "LAZY"


class ContainersMode(Enum):
    WARM = "WARM"
    COLD = "COLD"