from unittest import TestCase
from unittest.mock import patch

from parameterized import parameterized

from samcli.lib.telemetry.agent_detector import Agent, AgentDetector, _is_agent


class TestAgentDetector(TestCase):
    @parameterized.expand(
        [
            (Agent.ClaudeCode, "CLAUDECODE", "1"),
            (Agent.Codex, "CODEX_SANDBOX", "seatbelt"),
            (Agent.Cursor, "CURSOR_AGENT", "1"),
            (Agent.GeminiCLI, "GEMINI_CLI", "1"),
            (Agent.Kiro, "TERM_PROGRAM", "kiro"),
            (Agent.Kiro, "AWS_EXECUTION_ENV", "AmazonQ-For-CLI Version/1.13.3"),
            (Agent.OpenCode, "OPENCODE", "1"),
            (Agent.GitHubCopilot, "COPILOT_AGENT_SESSION_ID", "0b8f6e2c-1a3d-4c9e-8f7a-2b1c0d9e8f7a"),
        ]
    )
    def test_is_agent(self, agent, env_var, env_var_value):
        self.assertTrue(_is_agent(agent, {env_var: env_var_value}))

    @parameterized.expand(
        [
            (Agent.ClaudeCode, "NOT_CLAUDECODE", "1"),
            (Agent.Codex, "NOT_CODEX_SANDBOX", "seatbelt"),
            (Agent.Cursor, "NOT_CURSOR_AGENT", "1"),
            # exact-name rule: GEMINI_CLI_HOME must not match Agent.GeminiCLI
            (Agent.GeminiCLI, "GEMINI_CLI_HOME", "1"),
            # shared-variable rule: a Lambda AWS_EXECUTION_ENV must not match Agent.Kiro
            (Agent.Kiro, "AWS_EXECUTION_ENV", "AWS_Lambda_python3.12"),
            # too-generic var: AGENT alone (no OPENCODE) must not match Agent.OpenCode
            (Agent.OpenCode, "AGENT", "1"),
        ]
    )
    def test_is_not_agent(self, agent, env_var, env_var_value):
        self.assertFalse(_is_agent(agent, {env_var: env_var_value}))

    @patch.dict("samcli.lib.telemetry.agent_detector.os.environ", {"CLAUDECODE": "1"}, clear=True)
    def test_detector_identifies_claude_code(self):
        self.assertEqual(AgentDetector().agent(), Agent.ClaudeCode)

    @patch.dict("samcli.lib.telemetry.agent_detector.os.environ", {"CODEX_SANDBOX": "seatbelt"}, clear=True)
    def test_detector_identifies_codex(self):
        self.assertEqual(AgentDetector().agent(), Agent.Codex)

    @patch.dict("samcli.lib.telemetry.agent_detector.os.environ", {"CURSOR_AGENT": "1"}, clear=True)
    def test_detector_identifies_cursor(self):
        self.assertEqual(AgentDetector().agent(), Agent.Cursor)

    @patch.dict("samcli.lib.telemetry.agent_detector.os.environ", {"GEMINI_CLI": "1"}, clear=True)
    def test_detector_identifies_gemini_cli(self):
        self.assertEqual(AgentDetector().agent(), Agent.GeminiCLI)

    @patch.dict("samcli.lib.telemetry.agent_detector.os.environ", {"TERM_PROGRAM": "kiro"}, clear=True)
    def test_detector_identifies_kiro_ide(self):
        self.assertEqual(AgentDetector().agent(), Agent.Kiro)

    @patch.dict(
        "samcli.lib.telemetry.agent_detector.os.environ",
        {"AWS_EXECUTION_ENV": "AmazonQ-For-CLI Version/1.13.3"},
        clear=True,
    )
    def test_detector_identifies_kiro_cli(self):
        self.assertEqual(AgentDetector().agent(), Agent.Kiro)

    @patch.dict(
        "samcli.lib.telemetry.agent_detector.os.environ",
        {"AWS_EXECUTION_ENV": "AWS_Lambda_python3.12"},
        clear=True,
    )
    def test_detector_does_not_identify_lambda_as_kiro(self):
        self.assertIsNone(AgentDetector().agent())

    @patch.dict("samcli.lib.telemetry.agent_detector.os.environ", {"OPENCODE": "1"}, clear=True)
    def test_detector_identifies_opencode(self):
        self.assertEqual(AgentDetector().agent(), Agent.OpenCode)

    @patch.dict(
        "samcli.lib.telemetry.agent_detector.os.environ",
        {"COPILOT_AGENT_SESSION_ID": "0b8f6e2c-1a3d-4c9e-8f7a-2b1c0d9e8f7a"},
        clear=True,
    )
    def test_detector_identifies_github_copilot(self):
        self.assertEqual(AgentDetector().agent(), Agent.GitHubCopilot)

    @patch.dict("samcli.lib.telemetry.agent_detector.os.environ", {}, clear=True)
    def test_detector_returns_none_when_no_agent(self):
        self.assertIsNone(AgentDetector().agent())
