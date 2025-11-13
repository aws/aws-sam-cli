"""
Unit tests for Container Client Strategy Pattern

This module tests the ContainerClient abstract base class, DockerContainerClient
and FinchContainerClient implementations.
"""

import io
import os
from unittest import TestCase
from unittest.mock import Mock, patch

import docker
from parameterized import parameterized

from samcli.local.docker.container_client import (
    ContainerClient,
    DockerContainerClient,
    FinchContainerClient,
)
from samcli.local.docker.exceptions import (
    ContainerArchiveImageLoadFailedException,
    ContainerInvalidSocketPathException,
)
from samcli.lib.constants import DOCKER_MIN_API_VERSION


class BaseContainerClientTestCase(TestCase):
    """Base test case with common helper methods for container client testing"""

    def setUp(self):
        """Set up common test fixtures"""
        self.finch_socket = "unix:///tmp/finch.sock"
        self.docker_socket = "unix:///var/run/docker.sock"
        self.docker_version = DOCKER_MIN_API_VERSION
        self.finch_version = 1.35  # TODO: Update when Finch updates to latest Docker API version

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
        with patch.dict("os.environ", {}, clear=True), patch(
            "samcli.local.docker.container_client.get_finch_socket_path", return_value=self.finch_socket
        ):
            client = DockerContainerClient()

        # Verify DockerClient.__init__ was called with expected parameters
        mock_docker_init.assert_called_once()
        call_kwargs = mock_docker_init.call_args.kwargs
        self.assertEqual(call_kwargs["version"], self.docker_version)

    @patch("docker.DockerClient.__init__", return_value=None)
    def test_init_success_with_docker_host(self, mock_docker_init):
        """Test DockerContainerClient init when DOCKER_HOST is set to Docker socket"""
        with patch.dict("os.environ", {"DOCKER_HOST": self.docker_socket}, clear=True), patch(
            "samcli.local.docker.container_client.get_finch_socket_path", return_value=self.finch_socket
        ):
            client = DockerContainerClient()

        # Verify DockerClient.__init__ was called with expected parameters
        mock_docker_init.assert_called_once()
        call_kwargs = mock_docker_init.call_args.kwargs
        self.assertEqual(call_kwargs["version"], self.docker_version)
        self.assertEqual(call_kwargs["base_url"], self.docker_socket)

    def test_init_raises_exception_when_docker_host_points_to_finch(self):
        """Test DockerContainerClient init raises exception when DOCKER_HOST points to Finch socket"""
        with patch.dict("os.environ", {"DOCKER_HOST": self.finch_socket}, clear=True), patch(
            "samcli.local.docker.container_client.get_finch_socket_path", return_value=self.finch_socket
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
        with patch.dict("os.environ", {"DOCKER_HOST": docker_host}, clear=True), patch(
            "samcli.local.docker.container_client.get_finch_socket_path", return_value=self.finch_socket
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
        with patch("samcli.local.docker.container_client.get_finch_socket_path", return_value=self.finch_socket):
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
            client = ConcreteContainerClient(client_version=self.docker_version)

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
            client = ConcreteContainerClient(client_version=self.docker_version, base_url=override_url)

        # Verify DockerClient.__init__ was called with expected parameters
        mock_docker_init.assert_called_once()
        call_kwargs = mock_docker_init.call_args.kwargs
        self.assertEqual(call_kwargs["version"], self.docker_version)
        self.assertEqual(call_kwargs["base_url"], override_url)
        self.assertTrue(mock_log.debug.called)


class TestContainerClientBaseClass(TestCase):
    """Test the ContainerClient base class methods"""

    def setUp(self):
        """Set up test fixtures"""
        # Create a mock client that doesn't inherit from docker.DockerClient
        self.client = Mock(spec=ContainerClient)

        # Set up the methods we need to test
        self.client.is_available = ContainerClient.is_available.__get__(self.client)
        self.client.is_finch = ContainerClient.is_finch.__get__(self.client)
        self.client.is_docker = ContainerClient.is_docker.__get__(self.client)

        # Set up the mocked docker client attributes
        self.client.ping = Mock(return_value=True)
        self.client.get_runtime_type = Mock(return_value="docker")

    def test_is_available_success(self):
        """Test is_available returns True when ping succeeds"""
        self.client.ping.return_value = True
        self.assertTrue(self.client.is_available())

    @patch("samcli.local.docker.container_client.LOG")
    def test_is_available_failure(self, mock_log):
        """Test is_available returns False when ping fails and logs debug"""
        self.client.ping.side_effect = Exception("Connection failed")
        self.assertFalse(self.client.is_available())
        mock_log.debug.assert_called_once()

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
