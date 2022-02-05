import os
import threading
import time
from subprocess import Popen, PIPE
from typing import Optional, List
from unittest import TestCase


RETRY_COUNT = 20  # retry required because of log buffering configuration for each service
RETRY_SLEEP = 2


class LogsIntegBase(TestCase):

    def base_command(self):
        command = "sam"
        if os.getenv("SAM_CLI_DEV"):
            command = "samdev"

        return command

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
            output: Optional[str] = None,
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
        if output:
            command_list += ["--output", output]
        if beta_features:
            command_list += ["--beta-features"]

        return command_list
