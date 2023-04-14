from typing import List, Optional
from unittest import TestCase

from tests.testing_utils import get_sam_command


class DocsIntegBase(TestCase):
    @staticmethod
    def get_docs_command_list(sub_commands: Optional[List[str]] = None):
        command = [get_sam_command(), "docs"]

        if sub_commands:
            command += sub_commands

        return command
