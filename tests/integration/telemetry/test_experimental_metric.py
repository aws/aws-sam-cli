import os
import platform
import time
from pathlib import Path
from unittest.mock import ANY

from .integ_base import IntegBase, TelemetryServer
from samcli import __version__ as SAM_CLI_VERSION


class TestExperimentalMetric(IntegBase):
    """
    Validates the basic tenets/contract Telemetry module needs to adhere to
    """

    def test_must_send_experimental_metrics_if_experimental_command(self):
        """
        Metrics should be sent if "Disabled via config file but Enabled via Envvar"
        """
        # Disable it via configuration file
        self.unset_config()
        self.set_config(telemetry_enabled=True)
        os.environ["SAM_CLI_BETA_FEATURES"] = "0"
        os.environ["SAM_CLI_BETA_ACCELERATE"] = "1"

        with TelemetryServer() as server:
            # Run without any envvar.Should not publish metrics
            process = self.run_cmd(cmd_list=[self.cmd, "traces", "--trace-id", "random-trace"], optout_envvar_value="1")
            stdout, stderr = process.communicate()

            self.assertEqual(process.returncode, 1, "Command should fail")
            print(stdout)
            print(stderr)
            all_requests = server.get_all_requests()
            self.assertEqual(1, len(all_requests), "Command run metric must be sent")
            request = all_requests[0]
            self.assertIn("Content-Type", request["headers"])
            self.assertEqual(request["headers"]["Content-Type"], "application/json")

            expected_data = {
                "metrics": [
                    {
                        "commandRunExperimental": {
                            "requestId": ANY,
                            "installationId": self.get_global_config().installation_id,
                            "sessionId": ANY,
                            "executionEnvironment": ANY,
                            "ci": ANY,
                            "pyversion": ANY,
                            "samcliVersion": SAM_CLI_VERSION,
                            "awsProfileProvided": ANY,
                            "debugFlagProvided": ANY,
                            "region": ANY,
                            "commandName": ANY,
                            "metricSpecificAttributes": {
                                "experimentalAccelerate": True,
                                "experimentalAll": False,
                            },
                            "duration": ANY,
                            "exitReason": ANY,
                            "exitCode": ANY,
                        }
                    }
                ]
            }
            self.assertEqual(request["data"], expected_data)

    def test_must_send_experimental_metrics_if_experimental_option(self):
        """
        Metrics should be sent if "Disabled via config file but Enabled via Envvar"
        """
        # Disable it via configuration file
        self.unset_config()
        self.set_config(telemetry_enabled=True)
        os.environ["SAM_CLI_BETA_FEATURES"] = "1"

        with TelemetryServer() as server:
            # Run without any envvar.Should not publish metrics
            process = self.run_cmd(cmd_list=[self.cmd, "logs", "--include-traces"], optout_envvar_value="1")
            process.communicate()

            self.assertEqual(process.returncode, 1, "Command should fail")
            all_requests = server.get_all_requests()
            self.assertEqual(1, len(all_requests), "Command run metric must be sent")
            request = all_requests[0]
            self.assertIn("Content-Type", request["headers"])
            self.assertEqual(request["headers"]["Content-Type"], "application/json")

            expected_data = {
                "metrics": [
                    {
                        "commandRunExperimental": {
                            "requestId": ANY,
                            "installationId": self.get_global_config().installation_id,
                            "sessionId": ANY,
                            "executionEnvironment": ANY,
                            "ci": ANY,
                            "pyversion": ANY,
                            "samcliVersion": SAM_CLI_VERSION,
                            "awsProfileProvided": ANY,
                            "debugFlagProvided": ANY,
                            "region": ANY,
                            "commandName": ANY,
                            "metricSpecificAttributes": {
                                "experimentalAccelerate": True,
                                "experimentalAll": True,
                            },
                            "duration": ANY,
                            "exitReason": ANY,
                            "exitCode": ANY,
                        }
                    }
                ]
            }
            self.assertEqual(request["data"], expected_data)

    def test_must_send_cdk_project_type_metrics(self):
        """
        Metrics should be sent if "Disabled via config file but Enabled via Envvar"
        """
        # Disable it via configuration file
        self.unset_config()
        self.set_config(telemetry_enabled=True)
        os.environ["SAM_CLI_BETA_FEATURES"] = "0"
        template_path = (
            Path(__file__)
            .resolve()
            .parents[1]
            .joinpath("testdata")
            .joinpath("telemetry")
            .joinpath("cdk")
            .joinpath("cdk_template.yaml")
        )
        with TelemetryServer() as server:
            # Run without any envvar.Should not publish metrics
            process = self.run_cmd(
                cmd_list=[self.cmd, "build", "--build-dir", self.config_dir, "--template", str(template_path)],
                optout_envvar_value="1",
            )
            process.communicate()

            all_requests = server.get_all_requests()
            self.assertEqual(1, len(all_requests), "Command run metric must be sent")
            request = all_requests[0]
            self.assertIn("Content-Type", request["headers"])
            self.assertEqual(request["headers"]["Content-Type"], "application/json")

            expected_data = {
                "metrics": [
                    {
                        "commandRun": {
                            "requestId": ANY,
                            "installationId": self.get_global_config().installation_id,
                            "sessionId": ANY,
                            "executionEnvironment": ANY,
                            "ci": ANY,
                            "pyversion": ANY,
                            "samcliVersion": SAM_CLI_VERSION,
                            "awsProfileProvided": ANY,
                            "debugFlagProvided": ANY,
                            "region": ANY,
                            "commandName": ANY,
                            "metricSpecificAttributes": {"projectType": "CDK"},
                            "duration": ANY,
                            "exitReason": ANY,
                            "exitCode": ANY,
                        }
                    }
                ]
            }
            self.assertEqual(request["data"], expected_data)

    def test_must_send_not_experimental_metrics_if_not_experimental(self):
        """
        Metrics should be sent if "Disabled via config file but Enabled via Envvar"
        """
        # Disable it via configuration file
        self.unset_config()
        self.set_config(telemetry_enabled=True)
        os.environ["SAM_CLI_BETA_FEATURES"] = "0"

        with TelemetryServer() as server:
            # Run without any envvar.Should not publish metrics
            process = self.run_cmd(cmd_list=[self.cmd, "logs", "--name", "abc"], optout_envvar_value="1")
            process.communicate()

            self.assertEqual(process.returncode, 1, "Command should fail")
            all_requests = server.get_all_requests()
            self.assertEqual(1, len(all_requests), "Command run metric must be sent")
            request = all_requests[0]
            self.assertIn("Content-Type", request["headers"])
            self.assertEqual(request["headers"]["Content-Type"], "application/json")

            expected_data = {
                "metrics": [
                    {
                        "commandRun": {
                            "requestId": ANY,
                            "installationId": self.get_global_config().installation_id,
                            "sessionId": ANY,
                            "executionEnvironment": ANY,
                            "ci": ANY,
                            "pyversion": ANY,
                            "samcliVersion": SAM_CLI_VERSION,
                            "awsProfileProvided": ANY,
                            "debugFlagProvided": ANY,
                            "region": ANY,
                            "commandName": ANY,
                            "duration": ANY,
                            "exitReason": ANY,
                            "exitCode": ANY,
                        }
                    }
                ]
            }
            self.assertEqual(request["data"], expected_data)
