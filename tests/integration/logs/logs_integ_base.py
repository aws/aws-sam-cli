import os
import threading
import time
from subprocess import Popen, PIPE
from typing import Optional, List
from unittest import TestCase


RETRY_COUNT = 20  # retry required because of log buffering configuration for each service


class LogsIntegBase(TestCase):

    def base_command(self):
        command = "sam"
        if os.getenv("SAM_CLI_DEV"):
            command = "samdev"

        return command

    def start_tail(self, command_list: List, expected_log_output):
        self.tail_process = Popen(command_list, stdout=PIPE)

        self.stop_reading_thread = False

        def read_sub_process_stdout():
            count = 0
            while not self.stop_reading_thread:
                line = self.tail_process.stdout.readline()
                if expected_log_output in line.decode("utf-8"):
                    self.stop_reading_thread = True
                if count > RETRY_COUNT:
                    self.fail(f"Tail can't find log line {expected_log_output}")
                time.sleep(1)
                count += 1

        self.read_threading = threading.Thread(target=read_sub_process_stdout)
        self.read_threading.start()
        return self.read_threading

    def get_logs_command_list(
            self,
            stack_name: str,
            name: Optional[str] = None,
            filter: Optional[str] = None,
            include_traces: bool = False,
            cw_log_groups: Optional[List] = None,
            tail: bool = False,
            start_time: Optional[str] = None,
            end_time: Optional[str] = None,
            beta_features: bool = False,
    ):
        command_list = [self.base_command(), "logs", "--stack-name", stack_name]

        if name:
            command_list += ["--name", name]
        if filter:
            command_list += ["--filter", filter]
        if include_traces:
            command_list += ["--include-traces"]
        if cw_log_groups:
            for cw_log_group in cw_log_groups:
                command_list += ["--cw-log-group", cw_log_group]
        if tail:
            command_list += ["--tail"]
        if start_time:
            command_list += ["--start-time", start_time]
        if end_time:
            command_list += ["--end-time", end_time]
        if beta_features:
            command_list += ["--beta-features"]

        return command_list
