from unittest import TestCase
from unittest.mock import patch

from parameterized import parameterized

from samcli.lib.telemetry.user_agent import USER_AGENT_ENV_VAR, get_user_agent_string


class TestUserAgent(TestCase):
    @parameterized.expand(
        [
            ("AWS_Toolkit-For-VSCode/1.62.0",),
            ("AWS-Toolkit-For-JetBrains/1.60-223",),
            ("AWS-Toolkit-For-JetBrains/1.60.0-223",),
            ("AWS-Toolkit-For-JetBrains0/1.60.0-223",),
            ("AWS-Toolkit-For-JetBrains/1.60.0-2230",),
        ]
    )
    def test_user_agent(self, agent_value):
        with patch("samcli.lib.telemetry.user_agent.os.environ", {USER_AGENT_ENV_VAR: agent_value}):
            self.assertEqual(get_user_agent_string(), agent_value)

    @parameterized.expand(
        [
            ("invalid_value",),  # not matching the format at all
            ("AWS_Toolkit-For-VSCode/1",),  # not matching semver version
            ("AWS_Toolkit-For-V$Code/1.1.0",),  # invalid char in the name
            ("AWS_Toolkit-For-VSCode/1.1.0-patch$",),  # invalid char in the version
            # too long product name (> 64)
            ("AWS_Toolkit-For-VSCodeAWS_Toolkit-For-VSCodeAWS_Toolkit-For-VSCode/1.1.0-patch$",),
            # too long version extension (> 16)
            ("AWS_Toolkit-For-VSCode/1.1.0-patchpatchpatchpatch",),
        ]
    )
    def test_user_agent_with_invalid_value(self, agent_value):
        with patch("samcli.lib.telemetry.user_agent.os.environ", {USER_AGENT_ENV_VAR: agent_value}):
            self.assertEqual(get_user_agent_string(), None)

    @patch("samcli.lib.telemetry.user_agent.os.environ", {})
    def test_user_agent_without_env_var(self):
        self.assertEqual(get_user_agent_string(), None)

    @patch("samcli.lib.telemetry.user_agent.os.environ", {USER_AGENT_ENV_VAR: ""})
    def test_user_agent_with_empty_env_var(self):
        self.assertEqual(get_user_agent_string(), None)
