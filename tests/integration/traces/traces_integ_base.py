import os
import threading
import time
from subprocess import Popen, PIPE
from typing import Optional, List
from unittest import TestCase

RETRY_COUNT = 20

class TracesIntegBase(TestCase):

    def base_command(self):
        command = "sam"
        if os.getenv("SAM_CLI_DEV"):
            command = "samdev"

        return command

    def start_tail(self, command_list: List, expected_trace_output):
        self.tail_process = Popen(command_list, stdout=PIPE)

        self.stop_reading_thread = False

        def read_sub_process_stdout():
            count = 0
            while not self.stop_reading_thread:
                line = self.tail_process.stdout.readline()
                if expected_trace_output in line.decode("utf-8"):
                    self.stop_reading_thread = True
                if count > RETRY_COUNT:
                    self.fail(f"Tail can't find trace line {expected_trace_output}")
                time.sleep(1)
                count += 1

        self.read_threading = threading.Thread(target=read_sub_process_stdout)
        self.read_threading.start()
        return self.read_threading

    def get_traces_command_list(
            self,
            trace_id: Optional[str] = None,
            start_time: Optional[str] = None,
            end_time: Optional[str] = None,
            tail: bool = False,
            unformatted: bool = False, #TODO: we have task to update this parameter, need to update here
            beta_features: bool = False,
    ):
        command_list = [self.base_command(), "traces"]

        if trace_id:
            command_list += ["--trace-id", trace_id]
        if start_time:
            command_list += ["--start-time", start_time]
        if end_time:
            command_list += ["--end-time", end_time]
        if unformatted:
            command_list += ["--unformatted"]
        if tail:
            command_list += ["--tail"]
        if beta_features:
            command_list += ["--beta-features"]

        return command_list