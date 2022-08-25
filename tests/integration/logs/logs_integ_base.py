import logging
from typing import Optional, List
from unittest import TestCase, skipIf

from tests.testing_utils import get_sam_command, RUNNING_ON_CI, RUNNING_TEST_FOR_MASTER_ON_CI, RUN_BY_CANARY

RETRY_COUNT = 20  # retry required because of log buffering configuration for each service
RETRY_SLEEP = 2

LOG = logging.getLogger(__name__)

SKIP_LOGS_TESTS = RUNNING_ON_CI and RUNNING_TEST_FOR_MASTER_ON_CI and not RUN_BY_CANARY


@skipIf(SKIP_LOGS_TESTS, "Skip logs tests in CI/CD only")
class LogsIntegBase(TestCase):
    @staticmethod
    def get_logs_command_list(
        stack_name: str,
        name: Optional[str] = None,
        filter: Optional[str] = None,
        include_traces: bool = False,
        cw_log_groups: Optional[List] = None,
        tail: bool = False,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        output: Optional[str] = None,
    ):
        command_list = [get_sam_command(), "logs", "--stack-name", stack_name]

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

        return command_list
