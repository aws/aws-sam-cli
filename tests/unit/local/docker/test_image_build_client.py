"""
Unit tests for ContainerBuildClient implementations

Tests SDKBuildClient and CLIBuildClient implementations of the ContainerBuildClient interface.
"""

import os
from unittest import TestCase
from unittest.mock import Mock, patch

import docker.errors

from samcli.local.docker.image_build_client import SDKBuildClient, CLIBuildClient


class TestSDKBuildClient(TestCase):
    """TestSDKBuildClient implementation"""

    def setUp(self):
        self.mock_container_client = Mock()
        self.client = SDKBuildClient(self.mock_container_client)
        self.base_build_args = {
            "path": os.path.join("path", "to", "context"),
            "dockerfile": "Dockerfile",
            "tag": "image:latest",
        }

    def test_build_image_uses_sdk(self):
        """Test that build_image calls conatiner_client.images.build with correct params"""
        mock_image = Mock()
        mock_logs = iter([{"stream": "Step 1/5\n"}])
        self.mock_container_client.images.build.return_value = (mock_image, mock_logs)

        build_args = self.base_build_args | {
            "platform": "linux/amd64",
            "buildargs": {"arg1": "value1"},
            "target": "production",
            "rm": False,
        }

        result = self.client.build_image(**build_args)

        self.mock_container_client.images.build.assert_called_once_with(**build_args)
        self.assertEqual(result, mock_logs)

    def test_build_image_minimal(self):
        """Test build_image with only required params"""
        mock_image = Mock()
        mock_logs = iter([])
        self.mock_container_client.images.build.return_value = (mock_image, mock_logs)

        result = self.client.build_image(**self.base_build_args)

        self.mock_container_client.images.build.assert_called_once_with(
            **self.base_build_args,
            rm=True,
        )

    def test_is_available_returns_true(self):
        """Test that is_available always returns True for SDK"""
        result = SDKBuildClient.is_available("docker")
        self.assertEqual(result, (True, None))

        result = SDKBuildClient.is_available("finch")
        self.assertEqual(result, (True, None))


class TestCLIBuildClient(TestCase):
    """Test CLIBuildClient implementation"""

    def setUp(self):
        self.docker_client = CLIBuildClient(engine_type="docker")
        self.finch_client = CLIBuildClient(engine_type="finch")

        self.base_build_args = {
            "path": os.path.join("path", "to", "context"),
            "dockerfile": "Dockerfile",
            "tag": "image:latest",
        }

    def test_init_stores_engine_type(self):
        """Test that __init__stores engine type correctly"""
        self.assertEqual(self.docker_client.engine_type, "docker")
        self.assertEqual(self.finch_client.engine_type, "finch")

        self.assertEqual(self.docker_client.cli_command, "docker")
        self.assertEqual(self.finch_client.cli_command, "finch")

    @patch("samcli.local.docker.image_build_client.subprocess.Popen")
    def test_build_image_docker_command(self, mock_popen):
        """Test that build_image constructs correct docker buildx command"""
        mock_process = Mock()
        mock_process.stdout = iter(["Step 1/5\n", "Successfully build abc123\n"])
        mock_process.returncode = 0
        mock_popen.return_value = mock_process

        logs = list(
            self.docker_client.build_image(
                **(
                    self.base_build_args
                    | {
                        "platform": "linux/amd64",
                        "buildargs": {"arg1": "value1"},
                        "target": "prod",
                        "rm": True,
                    }
                )
            )
        )

        expected_cmd = [
            "docker",
            "buildx",
            "build",
            "-f",
            os.path.join("path", "to", "context", "Dockerfile"),
            "-t",
            "image:latest",
            "--provenance=false",
            "--sbom=false",
            "--platform",
            "linux/amd64",
            "--build-arg",
            "arg1=value1",
            "--target",
            "prod",
            "--rm",
            os.path.join("path", "to", "context"),
        ]

        mock_popen.assert_called_once()
        actual_cmd = mock_popen.call_args[0][0]
        self.assertEqual(actual_cmd, expected_cmd)

    @patch("samcli.local.docker.image_build_client.subprocess.Popen")
    def test_build_image_finch_command(self, mock_popen):
        """Test that build_image constructs correct finch command"""
        mock_process = Mock()
        mock_process.stdout = iter(["Step 1/5\n", "Successfully build abc123\n"])
        mock_process.returncode = 0
        mock_popen.return_value = mock_process

        logs = list(self.finch_client.build_image(**self.base_build_args))

        expected_cmd = [
            "finch",
            "build",
            "-f",
            os.path.join("path", "to", "context", "Dockerfile"),
            "-t",
            "image:latest",
            "--rm",
            os.path.join("path", "to", "context"),
        ]

        mock_popen.assert_called_once()
        actual_cmd = mock_popen.call_args[0][0]
        self.assertEqual(actual_cmd, expected_cmd)

    @patch("samcli.local.docker.image_build_client.subprocess.Popen")
    def test_build_image_streams_output_as_dicts(self, mock_popen):
        """Test that output is streamed as dicts matching SDK format"""
        mock_process = Mock()
        mock_process.stdout = iter(["Step 1/5\n", "Successfully build abc123\n"])
        mock_process.returncode = 0
        mock_popen.return_value = mock_process

        logs = list(self.finch_client.build_image(**self.base_build_args))

        self.assertEqual(
            logs,
            [
                {"stream": "Step 1/5\n"},
                {"stream": "Successfully build abc123\n"},
            ],
        )
        expected_cmd = [
            "finch",
            "build",
            "-f",
            os.path.join("path", "to", "context", "Dockerfile"),
            "-t",
            "image:latest",
            "--rm",
            os.path.join("path", "to", "context"),
        ]
        actual_cmd = mock_popen.call_args[0][0]
        self.assertEqual(actual_cmd, expected_cmd)

    @patch("samcli.local.docker.image_build_client.subprocess.Popen")
    def test_build_image_handles_failure(self, mock_popen):
        """Test that build failures raise BuildError"""
        mock_process = Mock()
        mock_process.stdout = iter(["Step 1/5\n", "Error: build failed\n"])
        mock_process.returncode = 1
        mock_popen.return_value = mock_process

        with self.assertRaises(docker.errors.BuildError) as context:
            list(self.docker_client.build_image(**self.base_build_args))

        self.assertIn("Build failed with exit code 1", str(context.exception))
        self.assertEqual(context.exception.build_log, "Step 1/5\nError: build failed\n")

    @patch("samcli.local.docker.image_build_client.shutil.which")
    @patch("samcli.local.docker.image_build_client.subprocess.run")
    def test_is_available_docker_success(self, mock_run, mock_which):
        """Test is_available returns True when docker buildx is available"""
        mock_which.return_value = "/usr/bin/docker"
        mock_run.return_value = Mock(returncode=0)

        result = CLIBuildClient.is_available("docker")

        self.assertEqual(result, (True, None))
        mock_which.assert_called_once_with("docker")
        mock_run.assert_called_once_with(
            ["docker", "buildx", "version"],
            capture_output=True,
            check=False,
        )

    @patch("samcli.local.docker.image_build_client.shutil.which")
    def test_is_available_docker_cli_not_found(self, mock_which):
        """Test is_available returns False when docker CLI not found"""
        mock_which.return_value = None

        result = CLIBuildClient.is_available("docker")

        self.assertEqual(result, (False, "Docker CLI not found"))

    @patch("samcli.local.docker.image_build_client.shutil.which")
    @patch("samcli.local.docker.image_build_client.subprocess.run")
    def test_is_available_docker_buildx_not_found(self, mock_run, mock_which):
        """Test is_available returns False when buildx plugin not available"""
        mock_which.return_value = "/usr/bin/docker"
        mock_run.return_value = Mock(returncode=1)

        result = CLIBuildClient.is_available("docker")

        self.assertEqual(result, (False, "docker buildx plugin not available"))

    @patch("samcli.local.docker.image_build_client.shutil.which")
    @patch("samcli.local.docker.image_build_client.subprocess.run")
    def test_is_available_finch_success(self, mock_run, mock_which):
        """Test is_available returns True when finch CLI is available"""
        mock_which.return_value = "/usr/local/bin/finch"
        mock_run.return_value = Mock(returncode=0)

        result = CLIBuildClient.is_available("finch")

        self.assertEqual(result, (True, None))
        mock_which.assert_called_once_with("finch")
        mock_run.assert_called_once_with(
            ["finch", "version"],
            capture_output=True,
            check=False,
        )

    @patch("samcli.local.docker.image_build_client.shutil.which")
    def test_is_available_finch_not_found(self, mock_which):
        """Test is_available returns False when finch CLI not found"""
        mock_which.return_value = None

        result = CLIBuildClient.is_available("finch")

        self.assertEqual(result, (False, "Finch CLI not found"))

    def test_is_available_unknown_engine(self):
        """Test is_available returns False for unknown engine type"""
        result = CLIBuildClient.is_available("podman")

        self.assertEqual(result, (False, "Unknown engine type: podman"))
