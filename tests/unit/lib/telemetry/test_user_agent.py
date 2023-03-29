import os
from unittest import TestCase
from unittest.mock import patch

from samcli.lib.telemetry.user_agent import USER_AGENT_ENV_VAR, get_user_agent_string


PATCHED_USER_AGENT_VALUE = "AWS-Toolkit-For-VSCode/1.62.0"


class TestUserAgent(TestCase):
    @patch("samcli.lib.telemetry.user_agent.os.environ", {USER_AGENT_ENV_VAR: PATCHED_USER_AGENT_VALUE})
    def test_user_agent(self):
        self.assertEqual(get_user_agent_string(), PATCHED_USER_AGENT_VALUE)

    @patch("samcli.lib.telemetry.user_agent.os.environ", {})
    def test_user_agent_without_env_var(self):
        self.assertEqual(get_user_agent_string(), None)
