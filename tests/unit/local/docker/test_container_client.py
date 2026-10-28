"""
Unit tests for Container Client Strategy Pattern

This module tests the ContainerClient abstract base class, DockerContainerClient
and FinchContainerClient implementations.
"""

import io
import json
import os
import tempfile
from unittest import TestCase
from unittest.mock import Mock, patch

import docker
from parameterized import parameterized

from samcli.cli.global_config import GlobalConfig
from samcli.local.docker.container_client import (
    ContainerClient,
    DockerContainerClient,
    FinchContainerClient,
    _is_docker_config_readable,
    _missing_credential_helpers,
)
from samcli.local.docker import container_client as container_client_module
from samcli.local.docker.exceptions import (
    ContainerArchiveImageLoadFailedException,
    ContainerInvalidSocketPathException,
    ContainerImagePullFailedException,
)
from samcli.lib.constants import DOCKER_MIN_API_VERSION


class BaseContainerClientTestCase(TestCase):
    """Base test case with common helper methods for container client testing"""

    def setUp(self):
        """Set up common test fixtures"""
        self.finch_socket = "unix:///tmp/finch.sock"
        self.docker_socket = "unix:///var/run/docker.sock"
        self.docker_version = DOCKER_MIN_API_VERSION
        self.finch_version = DOCKER_MIN_API_VERSION  # TODO: Update when Finch updates to latest Docker API version

    def create_mock_container_client(self, client_class, methods_to_bind=None):
        """Create a mock container client with bound methods for testing."""
        client = Mock(spec=client_class)

        # Default methods to bind
        default_methods = [
            "get_runtime_type",
            "get_socket_path",
            "is_docker",
            "is_finch",
            "is_available",
            "load_image_from_archive",
            "is_dockerfile_error",
            "list_containers_by_image",
            "remove_image_safely",
            "validate_image_count",
            "get_archive",
        ]

        methods_to_bind = methods_to_bind or default_methods

        # Bind methods from the actual class
        for method_name in methods_to_bind:
            if hasattr(client_class, method_name):
                setattr(client, method_name, getattr(client_class, method_name).__get__(client))

        # Set up common mock attributes
        client.api = Mock()
        client.images = Mock()
        client.containers = Mock()
        client.ping = Mock(return_value=True)
        client.socket_path = None

        return client

    def create_mock_containers(self, container_configs):
        """Create mock containers with specified configurations."""
        containers = []
        for config in container_configs:
            container = Mock()

            # Set up image attributes
            if "tags" in config or "image_id" in config:
                container.image = Mock()
                container.image.tags = config.get("tags", [])
                container.image.id = config.get("image_id", "sha256:default")

            # Set up container attributes
            container.status = config.get("status", "running")
            container.id = config.get("id", f"container-{len(containers)}")

            containers.append(container)

        return containers


# Shared test implementation of ContainerClient for testing abstract base class
class ConcreteContainerClient(ContainerClient):
    """Concrete implementation of ContainerClient for testing purposes"""

    def is_available(self):
        return True

    def get_socket_path(self):
        return "unix:///var/run/docker.sock"

    def get_runtime_type(self):
        return "test"

    def get_archive(self, container_id, path):
        pass

    def is_dockerfile_error(self, error):
        pass

    def list_containers_by_image(self, image_name, all_containers=True):
        pass

    def load_image_from_archive(self, archive):
        pass

    def remove_image_safely(self, image_name, force=True):
        pass

    def validate_image_count(self, image_name, expected_count_range=(1, 2)):
        pass


class TestContainerClientAbstractClass(TestCase):
    """Test the ContainerClient abstract base class"""

    def test_cannot_instantiate_abstract_class(self):
        """Test that ContainerClient cannot be instantiated directly"""
        with self.assertRaises(TypeError):
            ContainerClient()

    def test_inherits_from_docker_client(self):
        """Test that ContainerClient inherits from docker.DockerClient"""
        self.assertTrue(issubclass(ContainerClient, docker.DockerClient))

    def test_abstract_methods_defined(self):
        """Test that all required abstract methods are defined"""
        abstract_methods = {
            "is_available",
            "get_runtime_type",
            "get_socket_path",
            "load_image_from_archive",
            "is_dockerfile_error",
            "list_containers_by_image",
            "get_archive",
            "remove_image_safely",
            "validate_image_count",
        }

        # Get abstract methods from the class
        actual_abstract_methods = set(ContainerClient.__abstractmethods__)

        self.assertEqual(abstract_methods, actual_abstract_methods)


class TestDockerContainerClientInit(BaseContainerClientTestCase):
    """Test the DockerContainerClient __init__ method"""

    @patch("docker.DockerClient.__init__", return_value=None)
    def test_init_success_no_docker_host(self, mock_docker_init):
        """Test DockerContainerClient init when no DOCKER_HOST is set"""
        with (
            patch.dict("os.environ", {}, clear=True),
            patch("samcli.local.docker.container_client.get_finch_socket_path", return_value=self.finch_socket),
        ):
            client = DockerContainerClient()

        # Verify DockerClient.__init__ was called with expected parameters
        mock_docker_init.assert_called_once()
        call_kwargs = mock_docker_init.call_args.kwargs
        self.assertEqual(call_kwargs["version"], self.docker_version)

    @patch("docker.DockerClient.__init__", return_value=None)
    def test_init_success_with_docker_host(self, mock_docker_init):
        """Test DockerContainerClient init when DOCKER_HOST is set to Docker socket"""
        with (
            patch.dict("os.environ", {"DOCKER_HOST": self.docker_socket}, clear=True),
            patch("samcli.local.docker.container_client.get_finch_socket_path", return_value=self.finch_socket),
        ):
            client = DockerContainerClient()

        # Verify DockerClient.__init__ was called with expected parameters
        mock_docker_init.assert_called_once()
        call_kwargs = mock_docker_init.call_args.kwargs
        self.assertEqual(call_kwargs["version"], self.docker_version)
        self.assertEqual(call_kwargs["base_url"], self.docker_socket)

    def test_init_raises_exception_when_docker_host_points_to_finch(self):
        """Test DockerContainerClient init raises exception when DOCKER_HOST points to Finch socket"""
        with (
            patch.dict("os.environ", {"DOCKER_HOST": self.finch_socket}, clear=True),
            patch("samcli.local.docker.container_client.get_finch_socket_path", return_value=self.finch_socket),
        ):
            with self.assertRaises(ContainerInvalidSocketPathException) as context:
                DockerContainerClient()

        self.assertIn("DOCKER_HOST is set to Finch socket path", str(context.exception))

    @parameterized.expand(
        [
            ("tcp://localhost:2375",),
            ("unix:///var/run/docker.sock",),
            ("tcp://host.docker.internal:2357",),
        ]
    )
    @patch("docker.DockerClient.__init__", return_value=None)
    @patch("samcli.local.docker.container_client.LOG")
    def test_init_with_various_docker_host_values(self, docker_host, mock_log, mock_docker_init):
        """Test DockerContainerClient init with various DOCKER_HOST values"""
        with (
            patch.dict("os.environ", {"DOCKER_HOST": docker_host}, clear=True),
            patch("samcli.local.docker.container_client.get_finch_socket_path", return_value=self.finch_socket),
        ):
            client = DockerContainerClient()

        # Verify DockerClient.__init__ was called with expected parameters
        mock_docker_init.assert_called_once()
        call_kwargs = mock_docker_init.call_args.kwargs
        self.assertEqual(call_kwargs["version"], self.docker_version)
        self.assertEqual(call_kwargs["base_url"], docker_host)

        # Verify log call
        mock_log.debug.assert_any_call(f"Creating Docker container client with base_url={docker_host}.")


class TestDockerContainerClient(BaseContainerClientTestCase):
    """Test the DockerContainerClient implementation"""

    def setUp(self):
        """Set up test fixtures"""
        super().setUp()
        self.client = self.create_mock_container_client(DockerContainerClient)

    @parameterized.expand(
        [
            ("get_runtime_type", "docker"),
            ("is_docker", True),
            ("is_finch", False),
        ]
    )
    def test_docker_client_runtime_properties(self, method_name, expected_value):
        """Test DockerContainerClient runtime-related properties"""
        method = getattr(self.client, method_name)
        result = method()
        self.assertEqual(result, expected_value)

    def test_is_available_when_ping_succeeds(self):
        """Test is_available() returns True when ping succeeds"""
        self.client.ping.return_value = True
        self.assertTrue(self.client.is_available())

    @parameterized.expand(
        [
            (docker.errors.APIError("Connection failed"),),
            (TimeoutError("Connection timeout"),),
            (ConnectionError("Connection refused"),),
            (Exception("Generic error"),),
        ]
    )
    def test_is_available_when_ping_fails(self, exception):
        """Test is_available() returns False when ping fails with various exceptions"""
        self.client.ping.side_effect = exception
        self.assertFalse(self.client.is_available())

    def test_load_image_from_archive_success(self):
        """Test successful image loading from archive"""
        mock_image = Mock()
        self.client.images.load.return_value = [mock_image]

        mock_archive = Mock()
        result = self.client.load_image_from_archive(mock_archive)

        self.assertEqual(result, mock_image)
        self.client.images.load.assert_called_once_with(mock_archive)

    def test_load_image_from_archive_multiple_images(self):
        """Test error handling when archive contains multiple images"""
        self.client.images.load.return_value = [Mock(), Mock()]
        mock_archive = Mock()

        with self.assertRaises(ContainerArchiveImageLoadFailedException) as context:
            self.client.load_image_from_archive(mock_archive)

        self.assertIn("single image", str(context.exception))

    def test_load_image_from_archive_empty_archive(self):
        """Test error handling when archive is empty"""
        self.client.images.load.return_value = []
        mock_archive = Mock()

        with self.assertRaises(ValueError):
            self.client.load_image_from_archive(mock_archive)

    def test_load_image_from_archive_api_error(self):
        """Test error handling when Docker API fails"""
        self.client.images.load.side_effect = docker.errors.APIError("Load failed")

        mock_archive = Mock()

        with self.assertRaises(ContainerArchiveImageLoadFailedException) as context:
            self.client.load_image_from_archive(mock_archive)

        self.assertIn("Load failed", str(context.exception))

    @parameterized.expand(
        [
            (
                docker.errors.APIError("Server error", response=Mock(status_code=500)),
                "Cannot locate specified Dockerfile",
                True,
            ),
            (docker.errors.APIError("Server error", response=Mock(status_code=500)), "Some other error", False),
            (
                docker.errors.APIError("Client error", response=Mock(status_code=400)),
                "Cannot locate specified Dockerfile",
                False,
            ),
            ("Cannot locate specified Dockerfile in /path", None, True),
            ("Some other error message", None, False),
            (ValueError("Some error"), None, False),
            (
                docker.errors.APIError("Server error", response=Mock(status_code=500)),
                None,
                False,
            ),
        ]
    )
    def test_is_dockerfile_error(self, error, explanation, expected):
        """Test dockerfile error detection for Docker"""
        if isinstance(error, docker.errors.APIError):
            error.is_server_error = error.response.status_code >= 500
            error.explanation = explanation

        result = self.client.is_dockerfile_error(error)
        self.assertEqual(result, expected)

    @parameterized.expand(
        [
            (True,),
            (False,),
        ]
    )
    def test_list_containers_by_image(self, all_containers):
        """Test listing containers by image using ancestor filter"""
        mock_containers = [Mock(), Mock()]
        self.client.containers.list.return_value = mock_containers

        result = self.client.list_containers_by_image("test-image", all_containers=all_containers)

        self.assertEqual(result, mock_containers)
        self.client.containers.list.assert_called_once_with(all=all_containers, filters={"ancestor": "test-image"})

    def test_remove_image_safely_with_explicit_force_true(self):
        """Test image removal with explicit force=True"""
        self.client.remove_image_safely("test-image", force=True)
        self.client.images.remove.assert_called_once_with("test-image", force=True)

    def test_remove_image_safely_with_default_force(self):
        """Test image removal with default force parameter (should default to True)"""
        self.client.remove_image_safely("test-image")
        self.client.images.remove.assert_called_once_with("test-image", force=True)

    def test_remove_image_safely_image_not_found(self):
        """Test image removal when image doesn't exist"""
        self.client.images.remove.side_effect = docker.errors.ImageNotFound("Image not found")

        # Should not raise exception
        self.client.remove_image_safely("test-image", force=True)

    @patch("samcli.local.docker.container_client.LOG")
    def test_remove_image_safely_api_error(self, mock_log):
        """Test image removal with API error"""
        self.client.images.remove.side_effect = docker.errors.APIError("Remove failed")

        # Should not raise exception, but should log warning
        self.client.remove_image_safely("test-image", force=True)
        mock_log.warning.assert_called_once()

    @parameterized.expand(
        [
            (2, (1, 3), True),
            (1, (1, 3), True),
            (3, (1, 3), True),
            (0, (1, 3), False),
            (4, (1, 3), False),
            (0, (0, 1), True),
            (1, (0, 1), True),
        ]
    )
    def test_validate_image_count(self, image_count, range_tuple, expected_result):
        """Test image count validation with various scenarios"""
        mock_images = [Mock() for _ in range(image_count)]
        self.client.images.list.return_value = mock_images

        result = self.client.validate_image_count("test-image", range_tuple)

        self.assertEqual(result, expected_result)
        self.client.images.list.assert_called_once_with(name="test-image")

    @patch("samcli.local.docker.container_client.LOG")
    def test_validate_image_count_api_error(self, mock_log):
        """Test image count validation with API error"""
        self.client.images.list.side_effect = docker.errors.APIError("List failed")

        result = self.client.validate_image_count("test-image", (1, 2))

        self.assertFalse(result)
        mock_log.warning.assert_called_once()

    def test_get_archive(self):
        """Test getting archive from container using container ID"""
        container_id = "test-container-id"
        path = "/path/to/extract"
        expected_result = (b"archive_data", {"metadata": "info"})

        # Mock the container and its get_archive method
        mock_container = Mock()
        mock_container.get_archive.return_value = expected_result
        self.client.containers.get.return_value = mock_container

        result = self.client.get_archive(container_id, path)

        self.assertEqual(result, expected_result)
        self.client.containers.get.assert_called_once_with(container_id)
        mock_container.get_archive.assert_called_once_with(path)

    @parameterized.expand(
        [
            ({}, ""),
            ({"DOCKER_HOST": "unix:///var/run/docker.sock"}, "unix:///var/run/docker.sock"),
            ({"DOCKER_HOST": "tcp://localhost:2375"}, "tcp://localhost:2375"),
            ({"DOCKER_HOST": ""}, ""),
        ]
    )
    @patch("samcli.local.docker.container_client.get_finch_socket_path")
    def test_get_socket_path_scenarios(self, env_vars, expected_result, mock_get_finch_socket_path):
        """Test get_socket_path with various DOCKER_HOST scenarios"""
        mock_get_finch_socket_path.return_value = "unix://~/.finch/finch.sock"

        with patch.dict("os.environ", env_vars, clear=True):
            result = self.client.get_socket_path()

        self.assertEqual(result, expected_result)

    @patch("samcli.local.docker.container_client.get_finch_socket_path")
    def test_get_socket_path_scenarios_finch_socket_raises_exception(self, mock_get_finch_socket_path):
        """Test get_socket_path raises exception when DOCKER_HOST is set to Finch socket"""
        mock_get_finch_socket_path.return_value = "unix://~/.finch/finch.sock"

        with patch.dict("os.environ", {"DOCKER_HOST": "unix://~/.finch/finch.sock"}, clear=True):
            # Should raise ContainerInvalidSocketPathException
            with self.assertRaises(ContainerInvalidSocketPathException) as context:
                self.client.get_socket_path()

            self.assertIn("DOCKER_HOST is set to Finch socket path", str(context.exception))

    @patch("samcli.local.docker.container_client.get_finch_socket_path")
    @patch.dict("os.environ", {"DOCKER_HOST": "unix:///var/run/docker.sock"}, clear=True)
    def test_get_socket_path_caching(self, mock_get_finch_socket_path):
        """Test that get_socket_path caches the result"""
        mock_get_finch_socket_path.return_value = "unix://~/.finch/finch.sock"

        # First call
        result1 = self.client.get_socket_path()
        # Second call should use cached value
        result2 = self.client.get_socket_path()

        self.assertEqual(result1, "unix:///var/run/docker.sock")
        self.assertEqual(result2, "unix:///var/run/docker.sock")
        # get_finch_socket_path should only be called once due to caching
        mock_get_finch_socket_path.assert_called_once()


class TestFinchContainerClient(BaseContainerClientTestCase):
    """Test the FinchContainerClient implementation"""

    def setUp(self):
        """Set up test fixtures"""
        super().setUp()
        # Include Finch-specific methods
        finch_methods = [
            "get_runtime_type",
            "get_socket_path",
            "is_docker",
            "is_finch",
            "load_image_from_archive",
            "is_dockerfile_error",
            "list_containers_by_image",
            "remove_image_safely",
            "validate_image_count",
            "get_archive",
            "_load_with_raw_api",
            "_get_archive_from_mount",
        ]
        self.client = self.create_mock_container_client(FinchContainerClient, finch_methods)

    @parameterized.expand(
        [
            ("get_runtime_type", "finch"),
            ("is_finch", True),
            ("is_docker", False),
        ]
    )
    def test_finch_client_runtime_properties(self, method_name, expected_value):
        """Test FinchContainerClient runtime-related properties"""
        method = getattr(self.client, method_name)
        result = method()
        self.assertEqual(result, expected_value)

    def test_load_image_from_archive_success(self):
        """Test successful image loading from archive"""
        mock_image = Mock()
        self.client.images.load.return_value = [mock_image]

        mock_archive = Mock()
        result = self.client.load_image_from_archive(mock_archive)

        self.assertEqual(result, mock_image)
        self.client.images.load.assert_called_once_with(mock_archive)

    @patch("samcli.local.docker.container_client.LOG")
    def test_load_image_from_archive_overlayfs_fallback_success(self, mock_log):
        """Test image loading with successful overlayfs fallback"""
        # First call fails, triggering fallback
        self.client.images.load.side_effect = docker.errors.APIError("overlayfs error")

        # Mock the raw API response
        mock_response = [
            {"stream": "Loading image..."},
            {"stream": "Loaded image: sha256:abc123"},
        ]
        self.client.api.load_image.return_value = mock_response

        # Mock the image retrieval
        mock_image = Mock()
        self.client.images.get.return_value = mock_image

        mock_archive = io.BytesIO(b"fake archive data")
        result = self.client.load_image_from_archive(mock_archive)

        self.assertEqual(result, mock_image)
        self.client.api.load_image.assert_called_once()
        self.client.images.get.assert_called_once_with("sha256:abc123")

    @parameterized.expand(
        [
            (docker.errors.APIError("Server error", response=Mock(status_code=500)), "no such file or directory", True),
            (docker.errors.APIError("Server error", response=Mock(status_code=500)), "Some other error", False),
            ("No such file or directory: /path/Dockerfile", None, True),
            ("NO SUCH FILE OR DIRECTORY", None, True),
            ("no such file or directory", None, True),
            ("Some other error message", None, False),
            (ValueError("Some error"), None, False),
        ]
    )
    def test_is_dockerfile_error(self, error, explanation, expected):
        """Test dockerfile error detection for Finch"""
        if isinstance(error, docker.errors.APIError):
            error.is_server_error = error.response.status_code >= 500
            error.explanation = explanation

        result = self.client.is_dockerfile_error(error)
        self.assertEqual(result, expected)

    def test_list_containers_by_image_success_by_tag(self):
        """Test listing containers by image tag with manual filtering"""
        containers = self.create_mock_containers(
            [
                {"tags": ["test-image:latest", "test-image:v1.0"], "image_id": "sha256:abc123"},
                {"tags": ["other-image:latest"], "image_id": "sha256:def456"},
                {"tags": ["test-image:v2.0"], "image_id": "sha256:ghi789"},
            ]
        )

        self.client.containers.list.return_value = containers
        result = self.client.list_containers_by_image("test-image", all_containers=True)

        # Should return containers 0 and 2 (both have test-image in tags)
        self.assertEqual(len(result), 2)
        self.assertIn(containers[0], result)
        self.assertIn(containers[2], result)
        self.assertNotIn(containers[1], result)

    @parameterized.expand(
        [
            (1, (1, 3), True),
            (2, (1, 3), True),
            (5, (1, 2), True),
            (0, (1, 3), False),
            (0, (0, 1), True),
        ]
    )
    def test_validate_image_count_flexible_validation(self, image_count, range_tuple, expected_result):
        """Test flexible image count validation for Finch"""
        mock_images = [Mock() for _ in range(image_count)]
        self.client.images.list.return_value = mock_images

        result = self.client.validate_image_count("test-image", range_tuple)

        self.assertEqual(result, expected_result)

    @patch("samcli.local.docker.container_client.LOG")
    def test_validate_image_count_api_error(self, mock_log):
        """Test validate_image_count with API error"""
        self.client.images.list.side_effect = docker.errors.APIError("List failed")

        result = self.client.validate_image_count("test-image", (1, 2))

        self.assertFalse(result)
        mock_log.warning.assert_called_once()

    def test_get_socket_path_first_call(self):
        """Test get_socket_path on first call"""
        with patch("samcli.local.docker.container_client.get_finch_socket_path", return_value=self.finch_socket):
            result = self.client.get_socket_path()

        self.assertEqual(result, self.finch_socket)

    def test_get_socket_path_caching(self):
        """Test that get_socket_path caches the result"""
        with patch("samcli.local.docker.container_client.get_finch_socket_path") as mock_get_finch:
            mock_get_finch.return_value = self.finch_socket

            # First call
            result1 = self.client.get_socket_path()
            # Second call should use cached value
            result2 = self.client.get_socket_path()

            self.assertEqual(result1, self.finch_socket)
            self.assertEqual(result2, self.finch_socket)
            # get_finch_socket_path should only be called once due to caching
            mock_get_finch.assert_called_once()

    def test_get_socket_path_with_none_result_raises_exception(self):
        """Test get_socket_path raises exception when get_finch_socket_path returns None"""
        with patch("samcli.local.docker.container_client.get_finch_socket_path", return_value=None):
            with self.assertRaises(ContainerInvalidSocketPathException) as context:
                self.client.get_socket_path()

            self.assertIn("Finch is not supported on current platform!", str(context.exception))

    def test_remove_image_safely_with_running_containers(self):
        """Test image removal with running container cleanup"""
        containers = self.create_mock_containers([{"status": "running", "id": "container1"}])

        with patch.object(self.client, "list_containers_by_image", return_value=containers):
            self.client.remove_image_safely("test-image", force=True)

        # Verify container was stopped and removed
        containers[0].stop.assert_called_once()
        containers[0].remove.assert_called_once_with(force=True)
        self.client.images.remove.assert_called_once_with("test-image", force=True)

    @patch("samcli.local.docker.container_client.LOG")
    def test_remove_image_safely_image_not_found(self, mock_log):
        """Test image removal when image is not found"""
        with patch.object(self.client, "list_containers_by_image", return_value=[]):
            self.client.images.remove.side_effect = docker.errors.ImageNotFound("Image not found")

            # Should not raise exception
            self.client.remove_image_safely("test-image", force=True)

            mock_log.debug.assert_called_once()

    @patch("samcli.local.docker.container_client.LOG")
    def test_list_containers_by_image_api_error(self, mock_log):
        """Test container listing with API error"""
        self.client.containers.list.side_effect = docker.errors.APIError("List failed")

        result = self.client.list_containers_by_image("test-image")

        self.assertEqual(result, [])
        mock_log.warning.assert_called_once()


class TestFinchContainerClientInit(BaseContainerClientTestCase):
    """Test the FinchContainerClient __init__ method"""

    @patch("docker.DockerClient.__init__", return_value=None)
    @patch("samcli.local.docker.container_client.LOG")
    def test_init_with_socket_path_success(self, mock_log, mock_docker_init):
        """Test FinchContainerClient init with socket path available"""
        with (
            patch("samcli.local.docker.container_client.get_finch_socket_path", return_value=self.finch_socket),
            patch("samcli.local.docker.container_client.get_finch_registry_config_path", return_value=None),
        ):
            client = FinchContainerClient()

        # Verify DockerClient.__init__ was called with expected parameters
        mock_docker_init.assert_called_once()
        call_kwargs = mock_docker_init.call_args.kwargs
        self.assertEqual(call_kwargs["version"], self.finch_version)
        self.assertEqual(call_kwargs["base_url"], self.finch_socket)

        # Verify log call
        mock_log.debug.assert_any_call(f"Creating Finch container client with base_url={self.finch_socket}")

    def test_init_no_socket_path_raises_exception(self):
        """Test FinchContainerClient init raises exception when no socket path available"""
        with patch("samcli.local.docker.container_client.get_finch_socket_path", return_value=None):
            with self.assertRaises(ContainerInvalidSocketPathException) as context:
                FinchContainerClient()

        self.assertIn("Finch is not supported on current platform!", str(context.exception))

    @patch("docker.DockerClient.__init__", return_value=None)
    def test_init_with_empty_socket_path_skips_docker_init(self, mock_docker_init):
        """Test FinchContainerClient init skips Docker initialization when socket path is empty

        This is a defensive test to ensure that if get_socket_path() ever returns
        an empty string (even though get_finch_socket_path() currently only returns
        a valid path or None), the FinchContainerClient.__init__ method skips calling
        super().__init__() instead of trying to create a client with an empty socket path.
        This prevents customers from breaking this assumption in future changes.
        """
        # Mock get_socket_path to return empty string directly to test the __init__ logic
        with patch.object(FinchContainerClient, "get_socket_path", return_value=""):
            result = FinchContainerClient()

            # The object is created but super().__init__() should not be called
            self.assertIsNotNone(result)
            mock_docker_init.assert_not_called()


class TestContainerClientBaseInit(BaseContainerClientTestCase):
    """Test the ContainerClient base class __init__ method"""

    @patch("docker.DockerClient.__init__", return_value=None)
    @patch("samcli.local.docker.container_client.LOG")
    def test_init_no_overrides(self, mock_log, mock_docker_init):
        """Test ContainerClient init with no environment overrides"""
        with patch.dict("os.environ", {}, clear=True):
            client = ConcreteContainerClient()

        # Verify DockerClient.__init__ was called with expected parameters
        mock_docker_init.assert_called_once()
        call_kwargs = mock_docker_init.call_args.kwargs
        self.assertEqual(call_kwargs["version"], self.docker_version)
        self.assertTrue(mock_log.debug.called)

    @patch("docker.DockerClient.__init__", return_value=None)
    @patch("samcli.local.docker.container_client.LOG")
    def test_init_with_base_url_override(self, mock_log, mock_docker_init):
        """Test ContainerClient init with base_url override"""
        override_url = "unix:///tmp/finch.sock"

        with patch.dict("os.environ", {}, clear=True):
            client = ConcreteContainerClient(base_url=override_url)

        # Verify DockerClient.__init__ was called with expected parameters
        mock_docker_init.assert_called_once()
        call_kwargs = mock_docker_init.call_args.kwargs
        self.assertEqual(call_kwargs["version"], self.docker_version)
        self.assertEqual(call_kwargs["base_url"], override_url)
        self.assertTrue(mock_log.debug.called)

    @patch("docker.DockerClient.__init__", return_value=None)
    def test_init_with_api_override(self, mock_docker_init):
        """Test ContainerClient init with api override"""
        override_api = "1.51"

        with patch.dict("os.environ", {GlobalConfig.DOCKER_API_ENV_VAR: override_api}, clear=True):
            client = ConcreteContainerClient()

        # Verify DockerClient.__init__ was called with expected parameters
        mock_docker_init.assert_called_once()
        call_kwargs = mock_docker_init.call_args.kwargs
        self.assertEqual(call_kwargs["version"], override_api)


class TestContainerClientBaseClass(TestCase):
    """Test the ContainerClient base class methods"""

    def setUp(self):
        """Set up test fixtures"""
        # Create a mock client that doesn't inherit from docker.DockerClient
        self.client = Mock(spec=ContainerClient)

        # Set up the methods we need to test
        self.client.is_finch = ContainerClient.is_finch.__get__(self.client)
        self.client.is_docker = ContainerClient.is_docker.__get__(self.client)

        # Set up the mocked docker client attributes
        self.client.ping = Mock(return_value=True)
        self.client.get_runtime_type = Mock(return_value="docker")

    def test_is_available_finch_success(self):
        """Test is_available returns True when ping succeeds"""
        self.client.ping.return_value = True
        # check finch
        self.client.is_available = FinchContainerClient.is_available.__get__(self.client)
        self.assertTrue(self.client.is_available())

    def test_is_available_docker_success(self):
        """Test is_available returns True when ping succeeds"""
        self.client.ping.return_value = True
        # check docker
        self.client.is_available = DockerContainerClient.is_available.__get__(self.client)
        self.assertTrue(self.client.is_available())

    @patch("samcli.local.docker.container_client.LOG")
    def test_is_available_finch_failure(self, mock_log):
        """Test is_available returns False when ping fails and logs debug"""
        self.client.is_available = FinchContainerClient.is_available.__get__(self.client)
        self.client.ping.side_effect = Exception("Connection failed")
        self.assertFalse(self.client.is_available())
        mock_log.debug.assert_called_once()

    @patch("samcli.local.docker.container_client.LOG")
    def test_is_available_docker_failure(self, mock_log):
        """Test is_available returns False when ping fails and logs debug"""
        self.client.is_available = DockerContainerClient.is_available.__get__(self.client)
        self.client.ping.side_effect = Exception("Connection failed")
        self.assertFalse(self.client.is_available())
        mock_log.debug.assert_called()

    @parameterized.expand(
        [
            ("is_finch", "finch", True),
            ("is_finch", "docker", False),
            ("is_docker", "docker", True),
            ("is_docker", "finch", False),
        ]
    )
    def test_runtime_type_detection(self, method_name, runtime_type, expected_result):
        """Test runtime type detection methods"""
        self.client.get_runtime_type.return_value = runtime_type
        method = getattr(self.client, method_name)
        result = method()
        self.assertEqual(result, expected_result)


class TestContainerClientPullImage(TestCase):
    """Test the shared ContainerClient.pull_image used by every image pull"""

    def setUp(self):
        container_client_module._warned_once.clear()
        self.addCleanup(container_client_module._warned_once.clear)
        self.client = Mock(spec=DockerContainerClient)
        self.client.api = Mock()
        for method in ("pull_image", "_request_pull", "_raise_on_streamed_pull_error", "_describe_pull_failure"):
            setattr(self.client, method, getattr(ContainerClient, method).__get__(self.client))

    def test_yields_progress_events(self):
        events = [{"status": "Pulling"}, {"status": "Downloaded"}]
        self.client.api.pull.return_value = iter(events)

        result = list(self.client.pull_image("public.ecr.aws/foo/bar", tag="1.0"))

        self.assertEqual(result, events)
        self.client.api.pull.assert_called_once_with("public.ecr.aws/foo/bar", tag="1.0", stream=True, decode=True)

    def test_raises_when_pull_request_fails(self):
        self.client.api.pull.side_effect = docker.errors.APIError("pull access denied")

        with self.assertRaises(ContainerImagePullFailedException) as context:
            self.client.pull_image("foo/bar")

        self.assertIn("pull access denied", str(context.exception))

    def test_raises_on_error_reported_in_stream(self):
        self.client.api.pull.return_value = iter(
            [{"status": "Pulling"}, {"error": "toomanyrequests: rate limit", "errorDetail": {}}]
        )

        progress = self.client.pull_image("foo/bar")
        self.assertEqual(next(progress), {"status": "Pulling"})
        with self.assertRaises(ContainerImagePullFailedException) as context:
            next(progress)

        self.assertIn("toomanyrequests", str(context.exception))

    def test_ignores_non_dict_events(self):
        self.client.api.pull.return_value = iter(["raw line"])

        self.assertEqual(list(self.client.pull_image("foo/bar")), ["raw line"])

    def test_falls_back_to_anonymous_pull_when_credential_helper_is_missing(self):
        events = [{"status": "Pulled"}]
        self.client.api.pull.side_effect = [
            docker.errors.DockerException(
                "Credentials store error: StoreError('docker-credential-desktop not installed or not available in PATH')"
            ),
            iter(events),
        ]

        with self.assertLogs("samcli.local.docker.container_client", level="WARNING") as logs:
            result = list(self.client.pull_image("public.ecr.aws/foo/bar", tag="1.0"))

        self.assertEqual(result, events)
        self.client.api.pull.assert_called_with(
            "public.ecr.aws/foo/bar", tag="1.0", stream=True, decode=True, auth_config={}
        )
        self.assertTrue(any("without credentials" in line for line in logs.output))

    def test_pull_image_and_wait_reads_the_whole_pull(self):
        progress = iter([{"status": "Pulling"}, {"status": "Pulled"}])
        self.client.api.pull.return_value = progress
        self.client.pull_image_and_wait = ContainerClient.pull_image_and_wait.__get__(self.client)

        self.client.pull_image_and_wait("public.ecr.aws/foo/bar:1.0")

        self.client.api.pull.assert_called_once_with("public.ecr.aws/foo/bar:1.0", tag=None, stream=True, decode=True)
        self.assertEqual(list(progress), [])

    def test_pull_image_and_wait_raises_on_streamed_error(self):
        self.client.api.pull.return_value = iter([{"error": "toomanyrequests: rate limit"}])
        self.client.pull_image_and_wait = ContainerClient.pull_image_and_wait.__get__(self.client)

        with self.assertRaises(ContainerImagePullFailedException):
            self.client.pull_image_and_wait("foo/bar")

    def test_credentials_store_warning_is_shown_once(self):
        store_error = docker.errors.DockerException("Credentials store error: StoreError('missing helper')")
        self.client.api.pull.side_effect = [store_error, iter([]), store_error, iter([])]

        with self.assertLogs("samcli.local.docker.container_client", level="WARNING") as logs:
            list(self.client.pull_image("foo/bar"))
            list(self.client.pull_image("foo/baz"))

        self.assertEqual(len(logs.output), 1)
        self.assertIn("private registries will fail", logs.output[0])

    def test_other_docker_errors_are_not_swallowed(self):
        self.client.api.pull.side_effect = docker.errors.DockerException("something else")

        with self.assertRaises(docker.errors.DockerException):
            self.client.pull_image("foo/bar")

        self.client.api.pull.assert_called_once()


VALID_AUTH = "QVdTOnRva2Vu"  # base64("AWS:token")


class RegistryCredentialTestCase(BaseContainerClientTestCase):
    """Shared fixtures: a temp registry config, a real docker-py APIClient, clean warning state"""

    def setUp(self):
        super().setUp()
        container_client_module._warned_once.clear()
        self.addCleanup(container_client_module._warned_once.clear)
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.config_path = os.path.join(self.temp_dir.name, "config.json")
        # Keep docker-py away from the real Docker client config of whoever runs the tests
        env = patch.dict(
            "os.environ",
            {"DOCKER_CONFIG": os.path.join(self.temp_dir.name, "docker-config"), "HOME": self.temp_dir.name},
        )
        env.start()
        self.addCleanup(env.stop)

    def write_config(self, config):
        with open(self.config_path, "w") as f:
            f.write(config if isinstance(config, str) else json.dumps(config))

    def create_finch_client(self, config_path, installed_helpers=()):
        """Create a FinchContainerClient around a real APIClient that never connects to a daemon."""
        installed = {f"docker-credential-{helper}" for helper in installed_helpers}
        api = docker.APIClient(base_url="unix:///nonexistent.sock", version=DOCKER_MIN_API_VERSION)
        with (
            patch("docker.DockerClient.__init__", return_value=None),
            patch("samcli.local.docker.container_client.get_finch_socket_path", return_value=self.finch_socket),
            patch("samcli.local.docker.container_client.get_finch_registry_config_path", return_value=config_path),
            patch(
                "samcli.local.docker.container_client.shutil.which",
                side_effect=lambda name: name if name in installed else None,
            ),
            patch.object(ContainerClient, "api", api, create=True),
        ):
            client = FinchContainerClient()
        return client, api

    @staticmethod
    def sends_credentials(api, registry):
        """Whether docker-py would send credentials for registry on a pull."""
        return docker.auth.get_config_header(api, registry) is not None


class TestContainerClientRegistryAuthConfig(RegistryCredentialTestCase):
    """Each runtime loads its registry credentials once, at client creation"""

    @patch("docker.DockerClient.__init__", return_value=None)
    @patch("samcli.local.docker.container_client.get_finch_socket_path")
    @patch.dict("os.environ", {}, clear=True)
    def test_docker_client_keeps_docker_py_credential_resolution(self, mock_finch_socket, mock_docker_init):
        mock_finch_socket.return_value = self.finch_socket

        with patch.object(ContainerClient, "api", create=True) as mock_api:
            DockerContainerClient()

        mock_api.reload_config.assert_not_called()

    def test_finch_client_uses_finch_registry_config(self):
        self.write_config({"auths": {"public.ecr.aws": {"auth": VALID_AUTH}}})

        client, api = self.create_finch_client(self.config_path)

        self.assertTrue(self.sends_credentials(api, "public.ecr.aws"))
        self.assertTrue(client._uses_finch_registry_config)

    @parameterized.expand([("platform_uses_docker_config", False), ("config_file_missing", True)])
    def test_finch_client_falls_back_to_docker_config(self, _name, has_path):
        client, api = self.create_finch_client(self.config_path if has_path else None)

        self.assertFalse(self.sends_credentials(api, "public.ecr.aws"))
        self.assertFalse(client._uses_finch_registry_config)

    @parameterized.expand(
        [
            ("invalid_json", "{not json"),
            ("not_an_object", "[]"),
            ("invalid_base64_auth", {"auths": {"x.io": {"auth": "%%%notbase64"}}}),
            ("non_dict_auth_entry", {"auths": {"x.io": "oops"}}),
        ]
    )
    def test_unusable_finch_config_keeps_finch_available(self, _name, config):
        self.write_config(config)

        with self.assertLogs("samcli.local.docker.container_client", level="WARNING") as logs:
            client, _ = self.create_finch_client(self.config_path)

        self.assertIsInstance(client, FinchContainerClient)
        self.assertFalse(client._uses_finch_registry_config)
        self.assertTrue(any("using the Docker client config instead" in line for line in logs.output))

    @parameterized.expand(
        [
            ("missing_credential_store", {"credsStore": "osxkeychain"}),
            (
                "missing_registry_helper",
                {
                    "auths": {"https://index.docker.io/v1/": {"auth": VALID_AUTH}},
                    "credHelpers": {"public.ecr.aws": "ecr-login"},
                },
            ),
        ]
    )
    def test_config_with_missing_helper_is_not_used(self, _name, config):
        self.write_config(config)

        with self.assertLogs("samcli.local.docker.container_client", level="WARNING") as logs:
            client, _ = self.create_finch_client(self.config_path)

        self.assertFalse(client._uses_finch_registry_config)
        self.assertTrue(any("docker-credential-" in line and "Install the helper" in line for line in logs.output))

    def test_installed_credential_store_is_used(self):
        self.write_config({"credsStore": "osxkeychain"})

        client, _ = self.create_finch_client(self.config_path, installed_helpers=("osxkeychain",))

        self.assertTrue(client._uses_finch_registry_config)


class TestRegistryCredentialWarnings(RegistryCredentialTestCase):
    """Warnings come from the selected runtime only, once per process, and say how to fix the setup"""

    @patch("samcli.local.docker.container_client._is_docker_config_readable", return_value=False)
    def test_finch_warns_once_when_docker_config_is_unreadable(self, mock_readable):
        client, _ = self.create_finch_client(None)

        with self.assertLogs("samcli.local.docker.container_client", level="WARNING") as logs:
            client.warn_about_registry_credentials()
            client.warn_about_registry_credentials()

        self.assertEqual(len(logs.output), 1)
        self.assertIn("cannot be read by the current user", logs.output[0])
        self.assertIn("without sudo", logs.output[0])

    @patch("samcli.local.docker.container_client._is_docker_config_readable", return_value=False)
    def test_no_readability_warning_while_creating_the_client(self, mock_readable):
        with patch("samcli.local.docker.container_client.LOG") as mock_log:
            self.create_finch_client(None)

        mock_log.warning.assert_not_called()

    @patch("samcli.local.docker.container_client._is_docker_config_readable", return_value=False)
    def test_no_readability_warning_when_finch_config_is_used(self, mock_readable):
        self.write_config({"auths": {"public.ecr.aws": {"auth": VALID_AUTH}}})
        client, _ = self.create_finch_client(self.config_path)

        with patch("samcli.local.docker.container_client.LOG") as mock_log:
            client.warn_about_registry_credentials()

        mock_log.warning.assert_not_called()

    def test_docker_client_has_nothing_to_warn_about(self):
        client = Mock(spec=DockerContainerClient)

        with patch("samcli.local.docker.container_client.LOG") as mock_log:
            DockerContainerClient.warn_about_registry_credentials(client)

        mock_log.warning.assert_not_called()

    @parameterized.expand(
        [
            ("rate_limited", "toomanyrequests: Rate exceeded", True),
            ("finch_daemon_not_found", "no such image: public.ecr.aws/foo/bar: not found", True),
            ("unauthorized", "unexpected status code 401 Unauthorized", True),
            ("status_code_inside_digest", "sha256:9a4041c0f3: no space left on device", False),
            ("unrelated", "context deadline exceeded", False),
        ]
    )
    @patch("samcli.local.docker.container_client.get_finch_registry_config_path", return_value=None)
    def test_pull_failure_guidance(self, _name, error, expect_guidance, mock_config_path):
        client = Mock(spec=FinchContainerClient)
        message = FinchContainerClient._describe_pull_failure(client, error)

        self.assertTrue(message.startswith(error))
        self.assertEqual("finch login" in message, expect_guidance)

    def test_docker_client_pull_failure_is_unchanged(self):
        client = Mock(spec=DockerContainerClient)

        self.assertEqual(DockerContainerClient._describe_pull_failure(client, "toomanyrequests"), "toomanyrequests")


class TestDockerConfigReadability(TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.config_dir = os.path.join(self.temp_dir.name, ".docker")
        self.env = patch.dict("os.environ", {"DOCKER_CONFIG": self.config_dir})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.temp_dir.cleanup()

    def test_missing_config_is_readable(self):
        self.assertTrue(_is_docker_config_readable())

    def test_user_owned_config_is_readable(self):
        os.makedirs(self.config_dir)
        with open(os.path.join(self.config_dir, "config.json"), "w") as f:
            f.write("{}")

        self.assertTrue(_is_docker_config_readable())

    @parameterized.expand([("directory_not_accessible", True), ("file_not_readable", False)])
    def test_unreadable_config(self, _name, deny_directory):
        os.makedirs(self.config_dir)
        config_file = os.path.join(self.config_dir, "config.json")
        with open(config_file, "w") as f:
            f.write("{}")
        denied = self.config_dir if deny_directory else config_file

        with patch("samcli.local.docker.container_client.os.access", side_effect=lambda path, mode: path != denied):
            self.assertFalse(_is_docker_config_readable())


class TestRegistryConfigHelpers(TestCase):
    def test_missing_credential_helpers_reports_only_missing_ones(self):
        config = {"credsStore": "osxkeychain", "credHelpers": {"public.ecr.aws": "ecr-login", "x.io": "osxkeychain"}}
        installed = {"docker-credential-ecr-login"}

        with patch(
            "samcli.local.docker.container_client.shutil.which",
            side_effect=lambda name: name if name in installed else None,
        ):
            self.assertEqual(_missing_credential_helpers(config), ["osxkeychain"])

    def test_missing_credential_helpers_without_helpers(self):
        self.assertEqual(_missing_credential_helpers({"auths": {}}), [])
