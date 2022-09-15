import os
import platform
import time
from pathlib import Path
from unittest import skip
from unittest.mock import ANY

from .integ_base import IntegBase, TelemetryServer
from samcli import __version__ as SAM_CLI_VERSION


class TestExperimentalMetric(IntegBase):
    """
    Validates the basic tenets/contract Telemetry module needs to adhere to
    """

    @skip(
        "Accelerate are not in experimental any more, just skip this test. If we have new experimental commands, "
        "we can update this test"
    )
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
                                "experimentalAll": False,
                                "experimentalEsbuild": False,
                                "gitOrigin": ANY,
                                "projectName": ANY,
                                "initialCommit": ANY,
                            },
                            "duration": ANY,
                            "exitReason": ANY,
                            "exitCode": ANY,
                        }
                    }
                ]
            }
            self.assertEqual(request["data"], expected_data)
        os.environ["SAM_CLI_BETA_ACCELERATE"] = "0"

    @skip(
        "Accelerate are not in experimental any more, just skip this test. If we have new experimental commands, "
        "we can update this test"
    )
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

            self.assertEqual(process.returncode, 2, "Command should fail")
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
                                "experimentalAll": True,
                                "experimentalEsbuild": True,
                                "gitOrigin": ANY,
                                "projectName": ANY,
                                "initialCommit": ANY,
                            },
                            "duration": ANY,
                            "exitReason": ANY,
                            "exitCode": ANY,
                        }
                    }
                ]
            }
            self.assertEqual(request["data"], expected_data)
        os.environ["SAM_CLI_BETA_FEATURES"] = "0"

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
            self.assertGreaterEqual(len(all_requests), 1, "Command run metric must be sent")
            request = all_requests[0]
            for req in all_requests:
                if "commandRun" in req["data"]["metrics"][0]:
                    request = req  # We're only testing the commandRun metric
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
                            "metricSpecificAttributes": {
                                "projectType": "CDK",
                                "gitOrigin": ANY,
                                "projectName": ANY,
                                "initialCommit": ANY,
                            },
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

            self.assertEqual(process.returncode, 2, "Command should fail")
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
                            "metricSpecificAttributes": ANY,
                            "duration": ANY,
                            "exitReason": ANY,
                            "exitCode": ANY,
                        }
                    }
                ]
            }
            self.assertEqual(request["data"], expected_data)
