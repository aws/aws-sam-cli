from unittest import TestCase

from tests.testing_utils import get_sam_command


class InitIntegBase(TestCase):

    BINARY_READY_WAIT_TIME = 5

    def get_command(
        self,
    ):
        command_list = [get_sam_command(), "init"]
        return command_list
