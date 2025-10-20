"""
Unit tests for Container Client Strategy Pattern

This module tests the ContainerClient abstract base class, DockerContainerClient
and FinchContainerClient implementations, and ContainerClientFactory.
"""

import io
import os
from unittest import TestCase
from unittest.mock import Mock, patch, MagicMock, call, PropertyMock

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


class BaseContainerClientTestCase(TestCase):
    """Base test case with common helper methods for container client testing"""

    def setUp(self):
        """Set up common test fixtures"""
        self.finch_socket = "unix:///tmp/finch.sock"
        self.docker_socket = "unix:///var/run/docker.sock"
        self.default_version = "1.35"

    def create_mock_api_client(self, base_url=None):
        """Create a mock API client with standard configuration"""
        mock_api_instance = Mock()
        mock_api_instance.base_url = base_url or self.docker_socket
        return mock_api_instance

    def create_docker_client_spy(
        self, env_vars=None, expected_base_url=None, client_class=DockerContainerClient, finch_socket_path=None
    ):
        """
        Create a container client with constructor spy for testing initialization.

        Args:
            env_vars: Environment variables to set (default: empty)
            expected_base_url: Expected base_url in constructor call
            client_class: Container client class to instantiate
            finch_socket_path: Custom finch socket path (default: self.finch_socket)

        Returns:
            tuple: (client, spy_init) where spy_init contains constructor call info
        """
        env_vars = env_vars or {}
        finch_socket_path = finch_socket_path or self.finch_socket

        with patch("samcli.local.docker.container_client.get_finch_socket_path", return_value=finch_socket_path), patch(
            "os.environ", env_vars
        ), patch("docker.api.client.APIClient", return_value=self.create_mock_api_client(expected_base_url)):

            with patch.object(
                docker.DockerClient, "__init__", side_effect=docker.DockerClient.__init__, autospec=True
            ) as spy_init:
                client = client_class()

        return client, spy_init

    def assert_docker_client_init(self, spy_init, expected_base_url=None, expected_version=None):
        """Assert that Docker client was initialized with expected parameters"""
        expected_version = expected_version or self.default_version

        # Verify the constructor was called once
        spy_init.assert_called_once()

        # Get the call arguments
        call_args = spy_init.call_args
        args, kwargs = call_args.args[1:], call_args.kwargs  # Skip 'self' argument

        # Verify version parameter
        self.assertIn("version", kwargs)
        self.assertEqual(kwargs["version"], expected_version)

        # Verify base_url if expected
        if expected_base_url:
            self.assertIn("base_url", kwargs)
            self.assertEqual(kwargs["base_url"], expected_base_url)

    def assert_client_attributes(self, client, client_class):
        """Assert that client has expected Docker client attributes"""
        self.assertIsNotNone(client)
        self.assertIsInstance(client, client_class)
        self.assertTrue(hasattr(client, "api"))
        self.assertTrue(hasattr(client, "containers"))
        self.assertTrue(hasattr(client, "images"))

    def create_mock_container_client(self, client_class, methods_to_bind=None):
        """
        Create a mock container client with bound methods for testing.

        Args:
            client_class: The container client class to mock
            methods_to_bind: List of method names to bind from the class

        Returns:
            Mock client with bound methods
        """
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
        """
        Create mock containers with specified configurations.

        Args:
            container_configs: List of dicts with container configuration
                              Each dict can have: tags, image_id, status

        Returns:
            List of mock containers
        """
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

    def test_init_success_no_docker_host(self):
        """Test DockerContainerClient init when no DOCKER_HOST is set (empty string is valid)"""
        client, spy_init = self.create_docker_client_spy(env_vars={})

        self.assert_docker_client_init(spy_init)
        self.assert_client_attributes(client, DockerContainerClient)

    def test_init_success_with_docker_host(self):
        """Test DockerContainerClient init when DOCKER_HOST is set to Docker socket"""
        env_vars = {"DOCKER_HOST": self.docker_socket}
        client, spy_init = self.create_docker_client_spy(env_vars=env_vars, expected_base_url=self.docker_socket)

        self.assert_docker_client_init(spy_init, expected_base_url=self.docker_socket)
        self.assert_client_attributes(client, DockerContainerClient)

    def test_init_raises_exception_when_docker_host_points_to_finch(self):
        """Test DockerContainerClient init raises exception when DOCKER_HOST points to Finch socket"""
        env_vars = {"DOCKER_HOST": self.finch_socket}

        with patch("samcli.local.docker.container_client.get_finch_socket_path", return_value=self.finch_socket), patch(
            "os.environ", env_vars
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
    @patch("samcli.local.docker.container_client.LOG")
    def test_init_with_various_docker_host_values(self, docker_host, mock_log):
        """Test DockerContainerClient init with various DOCKER_HOST values"""
        env_vars = {"DOCKER_HOST": docker_host}
        client, spy_init = self.create_docker_client_spy(env_vars=env_vars, expected_base_url=docker_host)

        self.assert_docker_client_init(spy_init, expected_base_url=docker_host)
        self.assert_client_attributes(client, DockerContainerClient)

        # Verify log call
        mock_log.debug.assert_any_call(f"Creating Docker container client with base_url={docker_host}.")

    def test_init_with_finch_socket_raises_exception(self):
        """Test DockerContainerClient init raises exception when DOCKER_HOST matches Finch socket"""
        env_vars = {"DOCKER_HOST": self.finch_socket}

        with patch("samcli.local.docker.container_client.get_finch_socket_path", return_value=self.finch_socket), patch(
            "os.environ", env_vars
        ):
            with self.assertRaises(ContainerInvalidSocketPathException) as context:
                DockerContainerClient()

            self.assertIn("DOCKER_HOST is set to Finch socket path", str(context.exception))


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
            # Test with APIError containing dockerfile error
            (
                docker.errors.APIError("Server error", response=Mock(status_code=500)),
                "Cannot locate specified Dockerfile",
                True,
            ),
            # Test with APIError not containing dockerfile error
            (docker.errors.APIError("Server error", response=Mock(status_code=500)), "Some other error", False),
            # Test with client error (not server error)
            (
                docker.errors.APIError("Client error", response=Mock(status_code=400)),
                "Cannot locate specified Dockerfile",
                False,
            ),
            # Test with string containing dockerfile error
            ("Cannot locate specified Dockerfile in /path", None, True),
            # Test with string not containing dockerfile error
            ("Some other error message", None, False),
            # Test with other exception type
            (ValueError("Some error"), None, False),
            # Test with APIError and None explanation
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
            (2, (1, 3), True),  # Within range
            (1, (1, 3), True),  # At minimum
            (3, (1, 3), True),  # At maximum
            (0, (1, 3), False),  # Below minimum
            (4, (1, 3), False),  # Above maximum
            (0, (0, 1), True),  # Zero images within range
            (1, (0, 1), True),  # One image within range
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
            ({}, "", "no DOCKER_HOST set (should return empty string)"),
            ({"DOCKER_HOST": "unix:///var/run/docker.sock"}, "unix:///var/run/docker.sock", "Docker socket"),
            ({"DOCKER_HOST": "tcp://localhost:2375"}, "tcp://localhost:2375", "TCP socket"),
            ({"DOCKER_HOST": ""}, "", "empty DOCKER_HOST (should return empty string)"),
        ]
    )
    @patch("samcli.local.docker.container_client.get_finch_socket_path")
    def test_get_socket_path_scenarios(self, env_vars, expected_result, description, mock_get_finch_socket_path):
        """Test get_socket_path with various DOCKER_HOST scenarios"""
        mock_get_finch_socket_path.return_value = "unix://~/.finch/finch.sock"

        with patch.dict("os.environ", env_vars, clear=True):
            result = self.client.get_socket_path()

        self.assertEqual(result, expected_result, f"Failed for {description}")

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

    @parameterized.expand(
        [
            ("", "", "", "Both DOCKER_HOST and Finch socket are empty strings"),
            ("unix:///var/run/docker.sock", "", "unix:///var/run/docker.sock", "DOCKER_HOST set, Finch socket empty"),
            ("", "unix://~/.finch/finch.sock", "", "DOCKER_HOST empty, Finch socket set"),
            ("tcp://localhost:2375", "unix://~/.finch/finch.sock", "tcp://localhost:2375", "Different socket types"),
        ]
    )
    @patch("samcli.local.docker.container_client.get_finch_socket_path")
    def test_get_socket_path_finch_comparison_scenarios(
        self, docker_host, finch_socket, expected_result, description, mock_get_finch_socket_path
    ):
        """Test get_socket_path with various Finch socket comparison scenarios"""
        mock_get_finch_socket_path.return_value = finch_socket

        with patch.dict("os.environ", {"DOCKER_HOST": docker_host} if docker_host else {}, clear=True):
            result = self.client.get_socket_path()

        self.assertEqual(result, expected_result, f"Failed for {description}")

    @patch("samcli.local.docker.container_client.get_finch_socket_path")
    def test_get_socket_path_finch_comparison_docker_host_matches_finch(self, mock_get_finch_socket_path):
        """Test get_socket_path raises exception when DOCKER_HOST matches Finch socket"""
        finch_socket = "unix://~/.finch/finch.sock"
        mock_get_finch_socket_path.return_value = finch_socket

        with patch.dict("os.environ", {"DOCKER_HOST": finch_socket}, clear=True):
            # Should raise ContainerInvalidSocketPathException
            with self.assertRaises(ContainerInvalidSocketPathException) as context:
                self.client.get_socket_path()

            self.assertIn("DOCKER_HOST is set to Finch socket path", str(context.exception))

    @patch("samcli.local.docker.container_client.get_finch_socket_path")
    def test_get_socket_path_finch_returns_none(self, mock_get_finch_socket_path):
        """Test get_socket_path when get_finch_socket_path returns None"""
        mock_get_finch_socket_path.return_value = None

        with patch.dict("os.environ", {"DOCKER_HOST": "unix:///var/run/docker.sock"}, clear=True):
            result = self.client.get_socket_path()

        # Should return the DOCKER_HOST value since Finch socket is None
        self.assertEqual(result, "unix:///var/run/docker.sock")

    @patch("samcli.local.docker.container_client.get_finch_socket_path")
    def test_get_socket_path_raises_exception_when_docker_host_points_to_finch(self, mock_get_finch_socket_path):
        """Test that get_socket_path raises exception when DOCKER_HOST points to Finch socket"""
        mock_get_finch_socket_path.return_value = "unix:///tmp/finch.sock"

        with patch.dict("os.environ", {"DOCKER_HOST": "unix:///tmp/finch.sock"}, clear=True):
            # Should raise ContainerInvalidSocketPathException
            with self.assertRaises(ContainerInvalidSocketPathException) as context:
                self.client.get_socket_path()

            self.assertIn("DOCKER_HOST is set to Finch socket path", str(context.exception))

    @patch("samcli.local.docker.container_client.get_finch_socket_path")
    def test_get_socket_path_caching_with_empty_string(self, mock_get_finch_socket_path):
        """Test that get_socket_path caches empty string results correctly"""
        mock_get_finch_socket_path.return_value = "unix:///tmp/finch.sock"

        with patch.dict("os.environ", {}, clear=True):  # No DOCKER_HOST set
            # First call should return empty string and cache it
            result1 = self.client.get_socket_path()
            # Second call should use cached empty string value
            result2 = self.client.get_socket_path()

        self.assertEqual(result1, "")
        self.assertEqual(result2, "")
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

    def test_load_image_from_archive_overlayfs_fallback_no_digest(self):
        """Test overlayfs fallback when no valid digest is found"""
        self.client.images.load.side_effect = docker.errors.APIError("overlayfs error")

        # Mock response with overlayfs artifact
        mock_response = [
            {"stream": "Loading image..."},
            {"stream": "Loaded image: overlayfs:"},
        ]
        self.client.api.load_image.return_value = mock_response

        mock_archive = io.BytesIO(b"fake archive data")

        with self.assertRaises(ContainerArchiveImageLoadFailedException):
            self.client.load_image_from_archive(mock_archive)

    def test_load_image_from_archive_overlayfs_fallback_api_error(self):
        """Test overlayfs fallback when raw API also fails"""
        self.client.images.load.side_effect = docker.errors.APIError("overlayfs error")
        self.client.api.load_image.side_effect = docker.errors.APIError("Raw API also failed")

        mock_archive = io.BytesIO(b"fake archive data")

        with self.assertRaises(ContainerArchiveImageLoadFailedException):
            self.client.load_image_from_archive(mock_archive)

    @patch("samcli.local.docker.container_client.LOG")
    def test_load_image_from_archive_image_not_found_fallback(self, mock_log):
        """Test image loading with ImageNotFound triggering fallback"""
        # First call fails with ImageNotFound, triggering fallback
        self.client.images.load.side_effect = docker.errors.ImageNotFound("Image not found")

        # Mock the raw API response
        mock_response = [
            {"stream": "Loading image..."},
            {"stream": "Loaded image: sha256:def456"},
        ]
        self.client.api.load_image.return_value = mock_response

        # Mock the image retrieval
        mock_image = Mock()
        self.client.images.get.return_value = mock_image

        mock_archive = io.BytesIO(b"fake archive data")
        result = self.client.load_image_from_archive(mock_archive)

        self.assertEqual(result, mock_image)
        self.client.api.load_image.assert_called_once()
        self.client.images.get.assert_called_once_with("sha256:def456")

    def test_load_image_from_archive_multiple_images_error(self):
        """Test error when archive contains multiple images"""
        mock_image1 = Mock()
        mock_image2 = Mock()
        self.client.images.load.return_value = [mock_image1, mock_image2]

        mock_archive = Mock()

        with self.assertRaises(ContainerArchiveImageLoadFailedException) as context:
            self.client.load_image_from_archive(mock_archive)

        self.assertIn("single image", str(context.exception))

    @parameterized.expand(
        [
            # Test with APIError containing finch dockerfile error
            (docker.errors.APIError("Server error", response=Mock(status_code=500)), "no such file or directory", True),
            # Test with APIError not containing finch dockerfile error
            (docker.errors.APIError("Server error", response=Mock(status_code=500)), "Some other error", False),
            # Test with string containing finch dockerfile error (case variations)
            ("No such file or directory: /path/Dockerfile", None, True),
            ("NO SUCH FILE OR DIRECTORY", None, True),
            ("no such file or directory", None, True),
            # Test with string not containing finch dockerfile error
            ("Some other error message", None, False),
            # Test with other exception type
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

    def test_list_containers_by_image_success_by_id(self):
        """Test listing containers by image ID"""
        containers = self.create_mock_containers([{"tags": ["other-image:latest"], "image_id": "sha256:abc123"}])

        self.client.containers.list.return_value = containers
        result = self.client.list_containers_by_image("abc123", all_containers=True)

        self.assertEqual(len(result), 1)
        self.assertIn(containers[0], result)

    @patch("samcli.local.docker.container_client.LOG")
    def test_list_containers_by_image_inspection_error(self, mock_log):
        """Test container listing when container inspection fails"""
        container1 = Mock()
        container1.image = None  # This will cause an error during inspection

        container2 = Mock()
        container2.image.tags = ["test-image:latest"]

        self.client.containers.list.return_value = [container1, container2]

        result = self.client.list_containers_by_image("test-image", all_containers=True)

        # Should skip container1 and return container2
        self.assertEqual(len(result), 1)
        self.assertIn(container2, result)

    def test_list_containers_by_image_missing_image_attribute(self):
        """Test container listing when containers have missing image attributes"""
        container_with_image = Mock()
        container_with_image.image.tags = ["test-image:latest"]

        container_without_image = Mock()
        del container_without_image.image  # Simulate missing image attribute

        container_with_none_image = Mock()
        container_with_none_image.image = None

        self.client.containers.list.return_value = [
            container_with_image,
            container_without_image,
            container_with_none_image,
        ]

        result = self.client.list_containers_by_image("test-image")

        # Should only return the container with valid image
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0], container_with_image)

    @patch("samcli.local.docker.container_client.LOG")
    def test_list_containers_by_image_api_error(self, mock_log):
        """Test container listing with API error"""
        self.client.containers.list.side_effect = docker.errors.APIError("List failed")

        result = self.client.list_containers_by_image("test-image")

        self.assertEqual(result, [])
        mock_log.warning.assert_called_once()

    @patch("samcli.local.docker.container_client.LOG")
    def test_remove_image_safely_with_running_containers(self, mock_log):
        """Test image removal with running container cleanup"""
        containers = self.create_mock_containers([{"status": "running", "id": "container1"}])

        with patch.object(self.client, "list_containers_by_image", return_value=containers):
            self.client.remove_image_safely("test-image", force=True)

        # Verify container was stopped and removed
        containers[0].stop.assert_called_once()
        containers[0].remove.assert_called_once_with(force=True)
        self.client.images.remove.assert_called_once_with("test-image", force=True)

    @patch("samcli.local.docker.container_client.LOG")
    def test_remove_image_safely_with_exited_containers(self, mock_log):
        """Test image removal with exited container cleanup"""
        containers = self.create_mock_containers([{"status": "exited", "id": "container2"}])

        with patch.object(self.client, "list_containers_by_image", return_value=containers):
            self.client.remove_image_safely("test-image", force=True)

        # Verify container was removed but not stopped (already exited)
        containers[0].stop.assert_not_called()
        containers[0].remove.assert_called_once_with(force=True)
        self.client.images.remove.assert_called_once_with("test-image", force=True)

    @patch("samcli.local.docker.container_client.LOG")
    def test_remove_image_safely_container_stop_failure(self, mock_log):
        """Test image removal when container stop fails"""
        container = Mock()
        container.status = "running"
        container.id = "test-container"
        container.stop.side_effect = docker.errors.APIError("Stop failed")

        with patch.object(self.client, "list_containers_by_image", return_value=[container]):
            self.client.remove_image_safely("test-image")

        # Should try to stop the container, but when it fails, remove is skipped
        container.stop.assert_called_once()
        container.remove.assert_not_called()  # Remove is skipped due to exception

        # Should still try to remove the image
        self.client.images.remove.assert_called_once_with("test-image", force=True)

    @patch("samcli.local.docker.container_client.LOG")
    def test_remove_image_safely_container_remove_failure(self, mock_log):
        """Test image removal when container remove fails"""
        container = Mock()
        container.status = "running"
        container.remove.side_effect = docker.errors.APIError("Remove failed")

        with patch.object(self.client, "list_containers_by_image", return_value=[container]):
            self.client.remove_image_safely("test-image", force=True)

        # Should continue with image removal despite container cleanup failure
        self.client.images.remove.assert_called_once_with("test-image", force=True)

    @patch("samcli.local.docker.container_client.LOG")
    def test_remove_image_safely_image_not_found(self, mock_log):
        """Test image removal when image is not found"""
        # Mock no containers using the image
        with patch.object(self.client, "list_containers_by_image", return_value=[]):
            self.client.images.remove.side_effect = docker.errors.ImageNotFound("Image not found")

            # Should not raise exception
            self.client.remove_image_safely("test-image", force=True)

            mock_log.debug.assert_called_once()

    @patch("samcli.local.docker.container_client.LOG")
    def test_remove_image_safely_api_error(self, mock_log):
        """Test image removal with API error"""
        # Mock no containers using the image
        with patch.object(self.client, "list_containers_by_image", return_value=[]):
            self.client.images.remove.side_effect = docker.errors.APIError("Remove failed")

            # Should not raise exception, but should log warning
            self.client.remove_image_safely("test-image", force=True)

            mock_log.warning.assert_called_once()

    @parameterized.expand(
        [
            (1, (1, 3), True),  # Meets minimum
            (2, (1, 3), True),  # Above minimum
            (5, (1, 2), True),  # Finch uses flexible validation - passes if >= minimum
            (0, (1, 3), False),  # Below minimum
            (0, (0, 1), True),  # Zero images meets minimum of 0
        ]
    )
    def test_validate_image_count_flexible_validation(self, image_count, range_tuple, expected_result):
        """Test flexible image count validation for Finch"""
        mock_images = [Mock() for _ in range(image_count)]
        self.client.images.list.return_value = mock_images

        result = self.client.validate_image_count("test-image", range_tuple)

        self.assertEqual(result, expected_result)

    def test_get_archive_success(self):
        """Test successful get_archive with standard Docker API"""
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

    @patch("samcli.local.docker.container_client.LOG")
    def test_get_archive_finch_mount_fallback(self, mock_log):
        """Test get_archive with Finch mount fallback when standard API fails"""
        container_id = "test-container-id"
        path = "/tmp/samcli/artifacts"

        # Mock container that fails get_archive with Finch-specific error
        mock_container = Mock()
        mock_container.get_archive.side_effect = Exception("mount-snapshot error")
        mock_container.attrs = {
            "Mounts": [{"Type": "bind", "Source": "/host/tmp/samcli", "Destination": "/tmp/samcli"}]
        }
        self.client.containers.get.return_value = mock_container

        # Mock os.path.exists to return True for the host path
        with patch("os.path.exists", return_value=True), patch("tempfile.NamedTemporaryFile") as mock_temp, patch(
            "tarfile.open"
        ) as mock_tar:

            # Mock the temporary file and tar operations
            mock_temp_file = Mock()
            mock_temp_file.name = "/tmp/test.tar"
            mock_temp_file.seek = Mock()
            mock_temp_file.read.return_value = b"tar_data"
            mock_temp.return_value.__enter__.return_value = mock_temp_file

            mock_tar_obj = Mock()
            mock_tar.return_value.__enter__.return_value = mock_tar_obj

            result = self.client.get_archive(container_id, path)

            # Should return the tar data as an iterator
            self.assertEqual(result[1], {})  # Check metadata
            # Check that the first element is an iterator with the expected data
            result_data = list(result[0])
            self.assertEqual(result_data, [b"tar_data"])
            mock_log.debug.assert_called_once()

    @parameterized.expand(
        [
            ("no_artifacts", [{"Type": "bind", "Source": "/host/tmp/samcli", "Destination": "/tmp/samcli"}], False),
            ("no_samcli_mount", [{"Type": "bind", "Source": "/host/other", "Destination": "/other"}], True),
        ]
    )
    def test_get_archive_finch_mount_fallback_failures(self, failure_type, mounts, path_exists):
        """Test get_archive mount fallback failure scenarios"""
        container_id = "test-container-id"
        path = "/tmp/samcli/artifacts"

        # Mock container that fails get_archive
        mock_container = Mock()
        mock_container.get_archive.side_effect = Exception("mount-snapshot error")
        mock_container.attrs = {"Mounts": mounts}
        self.client.containers.get.return_value = mock_container

        # Mock os.path.exists based on test case
        with patch("os.path.exists", return_value=path_exists):
            with self.assertRaises(RuntimeError) as context:
                self.client.get_archive(container_id, path)

            self.assertIn("Could not find artifacts in Finch mounts", str(context.exception))

    def test_get_archive_non_finch_error_reraises(self):
        """Test get_archive re-raises non-Finch specific errors"""
        container_id = "test-container-id"
        path = "/path/to/extract"

        # Mock container that fails with non-Finch error
        mock_container = Mock()
        mock_container.get_archive.side_effect = Exception("Generic error")
        self.client.containers.get.return_value = mock_container

        with self.assertRaises(Exception) as context:
            self.client.get_archive(container_id, path)

        self.assertEqual(str(context.exception), "Generic error")

    @patch("samcli.local.docker.container_client.LOG")
    def test_validate_image_count_api_error(self, mock_log):
        """Test validate_image_count with API error"""
        self.client.images.list.side_effect = docker.errors.APIError("List failed")

        result = self.client.validate_image_count("test-image", (1, 2))

        self.assertFalse(result)
        mock_log.warning.assert_called_once()

    @patch("samcli.local.docker.container_client.get_finch_socket_path")
    def test_get_socket_path_first_call(self, mock_get_finch_socket_path):
        """Test get_socket_path on first call"""
        mock_get_finch_socket_path.return_value = "unix://~/.finch/finch.sock"

        result = self.client.get_socket_path()

        self.assertEqual(result, "unix://~/.finch/finch.sock")
        mock_get_finch_socket_path.assert_called_once()

    @patch("samcli.local.docker.container_client.get_finch_socket_path")
    def test_get_socket_path_caching(self, mock_get_finch_socket_path):
        """Test that get_socket_path caches the result"""
        mock_get_finch_socket_path.return_value = "unix://~/.finch/finch.sock"

        # First call
        result1 = self.client.get_socket_path()
        # Second call should use cached value
        result2 = self.client.get_socket_path()

        self.assertEqual(result1, "unix://~/.finch/finch.sock")
        self.assertEqual(result2, "unix://~/.finch/finch.sock")
        # get_finch_socket_path should only be called once due to caching
        mock_get_finch_socket_path.assert_called_once()

    @patch("samcli.local.docker.container_client.get_finch_socket_path")
    def test_get_socket_path_with_none_result_raises_exception(self, mock_get_finch_socket_path):
        """Test get_socket_path raises exception when get_finch_socket_path returns None"""
        mock_get_finch_socket_path.return_value = None

        with self.assertRaises(ContainerInvalidSocketPathException) as context:
            self.client.get_socket_path()

        self.assertIn("Finch is not supported on current platform!", str(context.exception))
        mock_get_finch_socket_path.assert_called_once()


class TestFinchContainerClientInit(BaseContainerClientTestCase):
    """Test the FinchContainerClient __init__ method"""

    @patch("samcli.local.docker.container_client.LOG")
    def test_init_with_socket_path_success(self, mock_log):
        """Test FinchContainerClient init with socket path available"""
        client, spy_init = self.create_docker_client_spy(
            expected_base_url=self.finch_socket, client_class=FinchContainerClient, finch_socket_path=self.finch_socket
        )

        self.assert_docker_client_init(spy_init, expected_base_url=self.finch_socket)
        self.assert_client_attributes(client, FinchContainerClient)

        # Verify log call
        mock_log.debug.assert_any_call(f"Creating Finch container client with base_url={self.finch_socket}")

    def test_init_no_socket_path_raises_exception(self):
        """Test FinchContainerClient init raises exception when no socket path available"""
        with patch("samcli.local.docker.container_client.get_finch_socket_path", return_value=None):
            with self.assertRaises(ContainerInvalidSocketPathException) as context:
                FinchContainerClient()

        self.assertIn("Finch is not supported on current platform!", str(context.exception))

    @parameterized.expand(
        [
            ("unix:///var/run/finch.sock",),
            ("unix:////Applications/Finch/lima/data/finch/sock/finch.sock",),
            ("tcp://localhost:2375",),
        ]
    )
    @patch("samcli.local.docker.container_client.LOG")
    def test_init_with_different_socket_paths(self, socket_path, mock_log):
        """Test FinchContainerClient init with various socket path formats"""
        client, spy_init = self.create_docker_client_spy(
            expected_base_url=socket_path, client_class=FinchContainerClient, finch_socket_path=socket_path
        )

        self.assert_docker_client_init(spy_init, expected_base_url=socket_path)
        self.assert_client_attributes(client, FinchContainerClient)

        # Verify log call
        mock_log.debug.assert_any_call(f"Creating Finch container client with base_url={socket_path}")


class TestContainerClientBaseInit(BaseContainerClientTestCase):
    """Test the ContainerClient base class __init__ method"""

    @patch("samcli.local.docker.container_client.LOG")
    def test_init_no_overrides(self, mock_log):
        """Test ContainerClient init with no environment overrides"""
        client, spy_init = self.create_docker_client_spy(env_vars={}, client_class=ConcreteContainerClient)

        self.assert_docker_client_init(spy_init)
        self.assert_client_attributes(client, ConcreteContainerClient)
        self.assertTrue(mock_log.debug.called)

    @patch("samcli.local.docker.container_client.LOG")
    def test_init_with_base_url_override(self, mock_log):
        """Test ContainerClient init with base_url override"""
        override_url = "unix:///tmp/finch.sock"

        with patch("docker.api.client.APIClient", return_value=self.create_mock_api_client(override_url)):
            with patch.object(
                docker.DockerClient, "__init__", side_effect=docker.DockerClient.__init__, autospec=True
            ) as spy_init:
                client = ConcreteContainerClient(base_url=override_url)

        self.assert_docker_client_init(spy_init, expected_base_url=override_url)
        self.assert_client_attributes(client, ConcreteContainerClient)
        self.assertTrue(mock_log.debug.called)

    @patch("samcli.local.docker.container_client.LOG")
    def test_init_override_precedence(self, mock_log):
        """Test that base_url parameter overrides environment variables"""
        override_url = "unix:///tmp/override.sock"

        with patch("os.environ", {"DOCKER_HOST": self.docker_socket}):
            with patch("docker.api.client.APIClient", return_value=self.create_mock_api_client(override_url)):
                with patch.object(
                    docker.DockerClient, "__init__", side_effect=docker.DockerClient.__init__, autospec=True
                ) as spy_init:
                    client = ConcreteContainerClient(base_url=override_url)

        self.assert_docker_client_init(spy_init, expected_base_url=override_url)
        self.assert_client_attributes(client, ConcreteContainerClient)

        # Verify that a log call was made
        self.assertTrue(mock_log.debug.called)

        # Verify the client was created successfully and has the expected attributes
        self.assertIsNotNone(client)
        self.assertIsInstance(client, ConcreteContainerClient)
        # Verify that the real Docker client attributes are present
        self.assertTrue(hasattr(client, "api"))
        self.assertTrue(hasattr(client, "containers"))
        self.assertTrue(hasattr(client, "images"))


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
            ("is_finch", "finch", True),  # is_finch returns True when runtime is finch
            ("is_finch", "docker", False),  # is_finch returns False when runtime is not finch
            ("is_docker", "docker", True),  # is_docker returns True when runtime is docker
            ("is_docker", "finch", False),  # is_docker returns False when runtime is not docker
        ]
    )
    def test_runtime_type_detection(self, method_name, runtime_type, expected_result):
        """Test runtime type detection methods"""
        self.client.get_runtime_type.return_value = runtime_type
        method = getattr(self.client, method_name)
        result = method()
        self.assertEqual(result, expected_result)


class TestContainerClientBehavioralDifferences(TestCase):
    """Test behavioral differences between Docker and Finch clients"""

    def setUp(self):
        """Set up test fixtures"""
        # Create mock clients
        self.docker_client = Mock(spec=DockerContainerClient)
        self.finch_client = Mock(spec=FinchContainerClient)

        # Set up Docker client methods
        self.docker_client.is_dockerfile_error = DockerContainerClient.is_dockerfile_error.__get__(self.docker_client)
        self.docker_client.list_containers_by_image = DockerContainerClient.list_containers_by_image.__get__(
            self.docker_client
        )
        self.docker_client.remove_image_safely = DockerContainerClient.remove_image_safely.__get__(self.docker_client)
        self.docker_client.validate_image_count = DockerContainerClient.validate_image_count.__get__(self.docker_client)
        self.docker_client.load_image_from_archive = DockerContainerClient.load_image_from_archive.__get__(
            self.docker_client
        )

        # Set up Finch client methods
        self.finch_client.is_dockerfile_error = FinchContainerClient.is_dockerfile_error.__get__(self.finch_client)
        self.finch_client.list_containers_by_image = FinchContainerClient.list_containers_by_image.__get__(
            self.finch_client
        )
        self.finch_client.remove_image_safely = FinchContainerClient.remove_image_safely.__get__(self.finch_client)
        self.finch_client.validate_image_count = FinchContainerClient.validate_image_count.__get__(self.finch_client)
        self.finch_client.load_image_from_archive = FinchContainerClient.load_image_from_archive.__get__(
            self.finch_client
        )
        self.finch_client._load_with_raw_api = FinchContainerClient._load_with_raw_api.__get__(self.finch_client)

        # Set up common mocks
        for client in [self.docker_client, self.finch_client]:
            client.api = Mock()
            client.images = Mock()
            client.containers = Mock()
            client.ping = Mock(return_value=True)

    def test_dockerfile_error_patterns_docker_specific(self):
        """Test Docker-specific dockerfile error detection"""
        docker_error = docker.errors.APIError("Server error", response=Mock(status_code=500))
        docker_error.is_server_error = True
        docker_error.explanation = "Cannot locate specified Dockerfile"

        finch_error = docker.errors.APIError("Server error", response=Mock(status_code=500))
        finch_error.is_server_error = True
        finch_error.explanation = "no such file or directory"

        # Docker should detect Docker-specific error but not Finch-specific
        self.assertTrue(self.docker_client.is_dockerfile_error(docker_error))
        self.assertFalse(self.docker_client.is_dockerfile_error(finch_error))

    def test_dockerfile_error_patterns_finch_specific(self):
        """Test Finch-specific dockerfile error detection"""
        docker_error = docker.errors.APIError("Server error", response=Mock(status_code=500))
        docker_error.is_server_error = True
        docker_error.explanation = "Cannot locate specified Dockerfile"

        finch_error = docker.errors.APIError("Server error", response=Mock(status_code=500))
        finch_error.is_server_error = True
        finch_error.explanation = "no such file or directory"

        # Finch should detect Finch-specific error but not Docker-specific
        self.assertTrue(self.finch_client.is_dockerfile_error(finch_error))
        self.assertFalse(self.finch_client.is_dockerfile_error(docker_error))

    def test_container_filtering_docker_uses_ancestor_filter(self):
        """Test Docker uses ancestor filter for container listing"""
        mock_containers = [Mock(), Mock()]
        self.docker_client.containers.list.return_value = mock_containers

        result = self.docker_client.list_containers_by_image("test-image")

        self.docker_client.containers.list.assert_called_with(all=True, filters={"ancestor": "test-image"})
        self.assertEqual(result, mock_containers)

    def test_container_filtering_finch_uses_manual_filtering(self):
        """Test Finch uses manual filtering for container listing"""
        mock_container = Mock()
        mock_container.image.tags = ["test-image:latest"]
        self.finch_client.containers.list.return_value = [mock_container]

        result = self.finch_client.list_containers_by_image("test-image")

        # Should call list without filters and do manual filtering
        self.finch_client.containers.list.assert_called_with(all=True)
        self.assertEqual(len(result), 1)

    def test_image_validation_docker_strict_vs_finch_flexible(self):
        """Test different image validation approaches between Docker and Finch"""
        mock_images = [Mock()]

        # Set up both clients with same image list
        self.docker_client.images.list.return_value = mock_images
        self.finch_client.images.list.return_value = mock_images

        # Docker uses strict validation (within range)
        docker_result = self.docker_client.validate_image_count("test-image", (2, 3))
        self.assertFalse(docker_result)  # 1 image not in range 2-3

        # Finch uses flexible validation (minimum only)
        finch_result = self.finch_client.validate_image_count("test-image", (1, 3))
        self.assertTrue(finch_result)  # 1 image meets minimum of 1

    def test_image_removal_cleanup_differences(self):
        """Test different image removal cleanup approaches"""
        # Docker: simple removal
        self.docker_client.remove_image_safely("test-image")
        self.docker_client.images.remove.assert_called_once_with("test-image", force=True)

        # Finch: container cleanup first
        mock_container = Mock()
        mock_container.status = "running"

        with patch.object(self.finch_client, "list_containers_by_image", return_value=[mock_container]):
            self.finch_client.remove_image_safely("test-image")

        # Should stop and remove container first, then image
        mock_container.stop.assert_called_once()
        mock_container.remove.assert_called_once_with(force=True)
        self.finch_client.images.remove.assert_called_once_with("test-image", force=True)

    def test_overlayfs_handling_difference(self):
        """Test overlayfs handling difference between Docker and Finch"""
        # Docker: no special overlayfs handling
        mock_image = Mock()
        self.docker_client.images.load.return_value = [mock_image]

        result = self.docker_client.load_image_from_archive(Mock())
        self.assertEqual(result, mock_image)

        # Finch: overlayfs fallback when standard loading fails
        self.finch_client.images.load.side_effect = docker.errors.APIError("overlayfs error")

        # Mock raw API response
        mock_response = [{"stream": "Loaded image: sha256:abc123"}]
        self.finch_client.api.load_image.return_value = mock_response
        self.finch_client.images.get.return_value = mock_image

        result = self.finch_client.load_image_from_archive(io.BytesIO(b"data"))

        # Should use raw API fallback
        self.finch_client.api.load_image.assert_called_once()
        self.finch_client.images.get.assert_called_once_with("sha256:abc123")
        self.assertEqual(result, mock_image)


class TestContainerClientEdgeCases(TestCase):
    """Test edge cases and error scenarios for container clients"""

    def setUp(self):
        """Set up test fixtures"""
        self.docker_client = Mock(spec=DockerContainerClient)
        self.finch_client = Mock(spec=FinchContainerClient)

        # Set up methods for both clients
        for client_class, client_instance in [
            (DockerContainerClient, self.docker_client),
            (FinchContainerClient, self.finch_client),
        ]:
            client_instance.is_available = client_class.is_available.__get__(client_instance)
            client_instance.load_image_from_archive = client_class.load_image_from_archive.__get__(client_instance)
            client_instance.is_dockerfile_error = client_class.is_dockerfile_error.__get__(client_instance)
            client_instance.list_containers_by_image = client_class.list_containers_by_image.__get__(client_instance)
            client_instance.remove_image_safely = client_class.remove_image_safely.__get__(client_instance)
            client_instance.validate_image_count = client_class.validate_image_count.__get__(client_instance)

            # Set up mocked attributes
            client_instance.api = Mock()
            client_instance.images = Mock()
            client_instance.containers = Mock()
            client_instance.ping = Mock()

        # Set up Finch-specific methods
        self.finch_client._load_with_raw_api = FinchContainerClient._load_with_raw_api.__get__(self.finch_client)

    @parameterized.expand(
        [
            ("docker", "docker_client"),
            ("finch", "finch_client"),
        ]
    )
    def test_client_ping_timeout(self, client_type, client_attr):
        """Test client availability check with timeout"""
        client = getattr(self, client_attr)
        client.ping.side_effect = TimeoutError("Connection timeout")

        result = client.is_available()

        self.assertFalse(result)

    @parameterized.expand(
        [
            ("docker", "docker_client"),
            ("finch", "finch_client"),
        ]
    )
    def test_client_ping_connection_error(self, client_type, client_attr):
        """Test client availability check with connection error"""
        client = getattr(self, client_attr)
        client.ping.side_effect = ConnectionError("Connection refused")

        result = client.is_available()

        self.assertFalse(result)

    def test_docker_load_image_empty_archive(self):
        """Test Docker image loading with empty archive"""
        self.docker_client.images.load.return_value = []

        with self.assertRaises(ValueError):
            self.docker_client.load_image_from_archive(Mock())

    def test_finch_load_image_corrupted_archive(self):
        """Test Finch image loading with corrupted archive that fails both methods"""
        self.finch_client.images.load.side_effect = docker.errors.APIError("Corrupted archive")
        self.finch_client.api.load_image.side_effect = docker.errors.APIError("Raw API also failed")

        with self.assertRaises(ContainerArchiveImageLoadFailedException):
            self.finch_client.load_image_from_archive(io.BytesIO(b"corrupted"))


class TestContainerClientIntegrationScenarios(BaseContainerClientTestCase):
    """Test integration scenarios that simulate real-world usage"""

    def setUp(self):
        """Set up test fixtures"""
        super().setUp()

        # Create mock clients with required methods
        common_methods = [
            "get_runtime_type",
            "is_docker",
            "is_finch",
            "load_image_from_archive",
            "list_containers_by_image",
            "remove_image_safely",
        ]
        finch_methods = common_methods + ["_load_with_raw_api"]

        self.docker_client = self.create_mock_container_client(DockerContainerClient, common_methods)
        self.finch_client = self.create_mock_container_client(FinchContainerClient, finch_methods)

    def test_sam_build_workflow_docker(self):
        """Test typical SAM build workflow with Docker client"""
        # Simulate loading a build image
        mock_image = Mock()
        self.docker_client.images.load.return_value = [mock_image]

        # Load image from archive
        result = self.docker_client.load_image_from_archive(Mock())
        self.assertEqual(result, mock_image)

        # Check runtime type for conditional logic
        self.assertEqual(self.docker_client.get_runtime_type(), "docker")
        self.assertTrue(self.docker_client.is_docker())

        # List containers for cleanup
        mock_containers = [Mock(), Mock()]
        self.docker_client.containers.list.return_value = mock_containers
        result = self.docker_client.list_containers_by_image("sam-build-image")
        self.assertEqual(result, mock_containers)

    def test_sam_build_workflow_finch(self):
        """Test typical SAM build workflow with Finch client"""
        # Simulate Finch overlayfs issue requiring fallback
        self.finch_client.images.load.side_effect = docker.errors.APIError("overlayfs error")

        # Mock successful raw API fallback
        mock_response = [{"stream": "Loaded image: sha256:abc123"}]
        self.finch_client.api.load_image.return_value = mock_response
        mock_image = Mock()
        self.finch_client.images.get.return_value = mock_image

        # Load image with fallback
        result = self.finch_client.load_image_from_archive(io.BytesIO(b"archive"))
        self.assertEqual(result, mock_image)

        # Check runtime type
        self.assertEqual(self.finch_client.get_runtime_type(), "finch")
        self.assertTrue(self.finch_client.is_finch())

        # List containers with manual filtering
        containers = self.create_mock_containers(
            [{"tags": ["sam-build-image:latest"]}, {"tags": ["other-image:latest"]}]
        )

        self.finch_client.containers.list.return_value = containers
        result = self.finch_client.list_containers_by_image("sam-build-image")

        # Should only return matching container
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0], containers[0])

    def test_cleanup_workflow_comparison(self):
        """Test cleanup workflow differences between Docker and Finch"""
        # Docker: simple cleanup
        self.docker_client.remove_image_safely("test-image")
        self.docker_client.images.remove.assert_called_once_with("test-image", force=True)

        # Finch: cleanup with container dependency handling
        containers = self.create_mock_containers([{"status": "running"}])

        with patch.object(self.finch_client, "list_containers_by_image", return_value=containers):
            self.finch_client.remove_image_safely("test-image")

        # Should stop and remove container first, then image
        containers[0].stop.assert_called_once()
        containers[0].remove.assert_called_once_with(force=True)
        self.finch_client.images.remove.assert_called_once_with("test-image", force=True)
