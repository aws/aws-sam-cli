import platform

from mock import ANY
from .integ_base import IntegBase, TelemetryServer, EXPECTED_TELEMETRY_PROMPT
from samcli import __version__ as SAM_CLI_VERSION


class TestSendInstalledMetric(IntegBase):
    def test_send_installed_metric_on_first_run(self):
        """
        On the first run, send the installed metric
        """
        self.unset_config()

        with TelemetryServer() as server:
            # Start the CLI
            process = self.run_cmd()

            (_, stderrdata) = process.communicate()

            retcode = process.poll()
            self.assertEquals(retcode, 0, "Command should successfully complete")

            # Make sure the prompt was printed. Otherwise this test is not valid
            self.assertIn(EXPECTED_TELEMETRY_PROMPT, stderrdata.decode())

            all_requests = server.get_all_requests()
            self.assertEquals(2, len(all_requests), "There should be exactly two metrics request")

            # First one is usually the installed metric
            requests = filter_installed_metric_requests(all_requests)
            self.assertEquals(1, len(requests), "There should be only one 'installed' metric")
            request = requests[0]
            self.assertIn("Content-Type", request["headers"])
            self.assertEquals(request["headers"]["Content-Type"], "application/json")

            expected_data = {
                "metrics": [
                    {
                        "installed": {
                            "installationId": self.get_global_config().installation_id,
                            "samcliVersion": SAM_CLI_VERSION,
                            "osPlatform": platform.system(),
                            "executionEnvironment": ANY,
                            "pyversion": ANY,
                            "sessionId": ANY,
                            "requestId": ANY,
                            "telemetryEnabled": True,
                        }
                    }
                ]
            }

            self.assertEquals(request["data"], expected_data)

    def test_must_not_send_installed_metric_when_prompt_is_disabled(self):
        """
        If the Telemetry Prompt is not displayed, we must *not* send installed metric, even if Telemetry is enabled.
        This happens on all subsequent runs.
        """

        # Enable Telemetry. This will skip the Telemetry Prompt.
        self.set_config(telemetry_enabled=True)

        with TelemetryServer() as server:
            # Start the CLI
            process = self.run_cmd()

            (stdoutdata, stderrdata) = process.communicate()

            retcode = process.poll()
            self.assertEquals(retcode, 0, "Command should successfully complete")
            self.assertNotIn(EXPECTED_TELEMETRY_PROMPT, stdoutdata.decode())
            self.assertNotIn(EXPECTED_TELEMETRY_PROMPT, stderrdata.decode())

            requests = filter_installed_metric_requests(server.get_all_requests())
            self.assertEquals(0, len(requests), "'installed' metric should NOT be sent")

    def test_must_not_send_installed_metric_on_second_run(self):
        """
        On first run, send installed metric. On second run, must *not* send installed metric
        """

        # Unset config to show the prompt
        self.unset_config()

        with TelemetryServer() as server:

            # First Run
            process1 = self.run_cmd()
            (_, stderrdata) = process1.communicate()
            retcode = process1.poll()
            self.assertEquals(retcode, 0, "Command should successfully complete")
            self.assertIn(EXPECTED_TELEMETRY_PROMPT, stderrdata.decode())
            self.assertEquals(
                1, len(filter_installed_metric_requests(server.get_all_requests())), "'installed' metric should be sent"
            )

            # Second Run
            process2 = self.run_cmd()
            (stdoutdata, stderrdata) = process2.communicate()
            retcode = process2.poll()
            self.assertEquals(retcode, 0)
            self.assertNotIn(EXPECTED_TELEMETRY_PROMPT, stdoutdata.decode())
            self.assertNotIn(EXPECTED_TELEMETRY_PROMPT, stderrdata.decode())
            self.assertEquals(
                1,
                len(filter_installed_metric_requests(server.get_all_requests())),
                "Only one 'installed' metric should be sent",
            )


def filter_installed_metric_requests(all_requests):

    result = []
    for r in all_requests:
        data = r["data"]
        if "metrics" in data and data["metrics"] and "installed" in data["metrics"][0]:
            result.append(r)

    return result
