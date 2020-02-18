from .integ_base import IntegBase, TelemetryServer


class TestTelemetryContract(IntegBase):
    """
    Validates the basic tenets/contract Telemetry module needs to adhere to
    """

    def test_must_not_send_metrics_if_disabled_using_envvar(self):
        """
        No metrics should be sent if "Enabled via Config file but Disabled via Envvar"
        """
        # Enable it via configuration file
        self.set_config(telemetry_enabled=True)

        with TelemetryServer() as server:
            # Start the CLI, but opt-out of Telemetry using env var
            process = self.run_cmd(optout_envvar_value="0")
            process.communicate()

            self.assertEqual(process.returncode, 0, "Command should successfully complete")
            all_requests = server.get_all_requests()
            self.assertEqual(0, len(all_requests), "No metrics should be sent")

            # Now run again without the Env Var Opt out
            process = self.run_cmd()
            process.communicate()

            self.assertEqual(process.returncode, 0, "Command should successfully complete")
            all_requests = server.get_all_requests()
            self.assertEqual(1, len(all_requests), "Command run metric should be sent")

    def test_must_send_metrics_if_enabled_via_envvar(self):
        """
        Metrics should be sent if "Disabled via config file but Enabled via Envvar"
        """
        # Disable it via configuration file
        self.set_config(telemetry_enabled=False)

        with TelemetryServer() as server:
            # Run without any envvar.Should not publish metrics
            process = self.run_cmd()
            process.communicate()

            self.assertEqual(process.returncode, 0, "Command should successfully complete")
            all_requests = server.get_all_requests()
            self.assertEqual(0, len(all_requests), "No metric should be sent")

            # Opt-in via env var
            process = self.run_cmd(optout_envvar_value="1")
            process.communicate()

            self.assertEqual(process.returncode, 0, "Command should successfully complete")
            all_requests = server.get_all_requests()
            self.assertEqual(1, len(all_requests), "Command run metric must be sent")

    def test_must_not_crash_when_offline(self):
        """
        Must not crash the process if internet is not available
        """
        self.set_config(telemetry_enabled=True)

        # DO NOT START Telemetry Server here.
        # Try to run the command without it.

        # Start the CLI
        process = self.run_cmd()

        process.communicate()

        self.assertEqual(process.returncode, 0, "Command should successfully complete")
