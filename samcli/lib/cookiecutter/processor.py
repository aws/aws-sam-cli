""" Define a processor to process the cookiecutter context before/after generating a cookiecutter project"""
from abc import ABC, abstractmethod
from typing import Dict


class Processor(ABC):
    """
    An abstract class for defining template's preprocessors and postprocessors
    """

    @abstractmethod
    def run(self, context: Dict) -> Dict:
        """
        the processing logic of this processor

        Parameters
        ----------
        context: Dict
            The cookiecutter context to process

        Returns: A processed copy of the cookiecutter context
        """
