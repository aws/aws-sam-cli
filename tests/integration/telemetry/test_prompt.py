from parameterized import parameterized
from .integ_base import IntegBase, EXPECTED_TELEMETRY_PROMPT


class TestTelemetryPrompt(IntegBase):
    def test_must_prompt_if_config_is_not_set(self):
        """
        Must print prompt if Telemetry config is not set.
        """
        self.unset_config()

        process = self.run_cmd()
        _, stderrdata = process.communicate()

        # Telemetry prompt should be printed to the terminal
        self.assertIn(EXPECTED_TELEMETRY_PROMPT, stderrdata.decode())

    @parameterized.expand([(True, "Enable Telemetry"), (False, "Disalbe Telemetry")])
    def test_must_not_prompt_if_config_is_set(self, telemetry_enabled, msg):
        """
        If telemetry config is already set, prompt must not be displayed
        """

        # Set the telemetry config
        self.set_config(telemetry_enabled=telemetry_enabled)

        process = self.run_cmd()
        stdoutdata, stderrdata = process.communicate()

        self.assertNotIn(EXPECTED_TELEMETRY_PROMPT, stdoutdata.decode())
        self.assertNotIn(EXPECTED_TELEMETRY_PROMPT, stderrdata.decode())

    def test_prompt_must_not_display_on_second_run(self):
        """
        On first run, display the prompt. Do *not* display prompt on subsequent runs.
        """
        self.unset_config()

        # First Run
        process = self.run_cmd()
        _, stderrdata = process.communicate()
        self.assertIn(EXPECTED_TELEMETRY_PROMPT, stderrdata.decode())

        # Second Run
        process = self.run_cmd()
        stdoutdata, stderrdata = process.communicate()
        self.assertNotIn(EXPECTED_TELEMETRY_PROMPT, stdoutdata.decode())
        self.assertNotIn(EXPECTED_TELEMETRY_PROMPT, stderrdata.decode())
