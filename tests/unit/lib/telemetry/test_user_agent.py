from unittest import TestCase
from unittest.mock import patch

from parameterized import parameterized

from samcli.lib.telemetry.user_agent import (
    ACCEPTED_USER_AGENT_FORMAT,
    USER_AGENT_ENV_VAR,
    get_user_agent_string,
)


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


class TestUserAgentAgentFallback(TestCase):
    # NOTE: user_agent.py and agent_detector.py both read os.environ, which is a
    # single shared object, so one patch.dict on os.environ controls the env seen
    # by both the toolkit lookup and the agent detector. clear=True keeps the
    # ambient CLAUDECODE of the running shell from leaking into these tests.
    @patch.dict("samcli.lib.telemetry.user_agent.os.environ", {"CLAUDECODE": "1"}, clear=True)
    def test_detected_agent_is_used_when_no_toolkit_user_agent(self):
        # No AWS_TOOLING_USER_AGENT set, Claude Code detected -> agent string is emitted.
        self.assertEqual(get_user_agent_string(), "claude-code/1.0")

    @parameterized.expand(
        [
            ("AWS_Toolkit-For-VSCode/1.62.0",),
            ("AWS-Toolkit-For-JetBrains/1.60-223",),
        ]
    )
    def test_toolkit_user_agent_takes_precedence_over_detected_agent(self, toolkit_user_agent):
        # A valid AWS_TOOLING_USER_AGENT wins even when an agent is detected.
        with patch.dict(
            "samcli.lib.telemetry.user_agent.os.environ",
            {"CLAUDECODE": "1", USER_AGENT_ENV_VAR: toolkit_user_agent},
            clear=True,
        ):
            self.assertEqual(get_user_agent_string(), toolkit_user_agent)

    @patch.dict(
        "samcli.lib.telemetry.user_agent.os.environ",
        {"CLAUDECODE": "1", USER_AGENT_ENV_VAR: "invalid_value"},
        clear=True,
    )
    def test_detected_agent_is_used_when_toolkit_user_agent_is_invalid(self):
        # An invalid AWS_TOOLING_USER_AGENT falls through to the detected agent.
        self.assertEqual(get_user_agent_string(), "claude-code/1.0")

    @patch.dict("samcli.lib.telemetry.user_agent.os.environ", {}, clear=True)
    def test_none_when_no_toolkit_user_agent_and_no_agent(self):
        self.assertEqual(get_user_agent_string(), None)

    @patch.dict("samcli.lib.telemetry.user_agent.os.environ", {"CLAUDECODE": "1"}, clear=True)
    def test_emitted_agent_string_matches_accepted_format(self):
        # Guard against emitting a bare "ClaudeCode": the fallback must satisfy the
        # same regex the toolkit user-agent must satisfy.
        self.assertIsNotNone(ACCEPTED_USER_AGENT_FORMAT.match(get_user_agent_string()))
