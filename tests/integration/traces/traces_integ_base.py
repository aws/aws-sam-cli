import threading
import time
from subprocess import Popen, PIPE
from typing import Optional, List
from unittest import TestCase
from tests.testing_utils import get_sam_command

RETRY_COUNT = 20
RETRY_SLEEP = 2


class TracesIntegBase(TestCase):
    @staticmethod
    def get_traces_command_list(
        trace_id: Optional[str] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        tail: bool = False,
        output: Optional[str] = None,
    ):
        command_list = [get_sam_command(), "traces"]

        if trace_id:
            command_list += ["--trace-id", trace_id]
        if start_time:
            command_list += ["--start-time", start_time]
        if end_time:
            command_list += ["--end-time", end_time]
        if output:
            command_list += ["--output", output]
        if tail:
            command_list += ["--tail"]

        return command_list
