from unittest import TestCase

from tests.testing_utils import get_sam_command


class DocsIntegBase(TestCase):
    @staticmethod
    def get_docs_command_list():
        return [get_sam_command(), "docs"]
