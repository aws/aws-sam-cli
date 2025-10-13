"""
Unit tests for Container Client Strategy Pattern

This module tests the ContainerClient abstract base class, DockerContainerClient
and FinchContainerClient implementations, and ContainerClientFactory.
"""

import io
import os
from unittest import TestCase
from unittest.mock import Mock, patch, MagicMock, call

import docker
from parameterized import parameterized

from samcli.local.docker.container_client import (
    ContainerClient,
    DockerContainerClient,
    FinchContainerClient,
)
from samcli.local.docker.exceptions import (
    ContainerArchiveImageLoadFailedException,
)


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


class TestDockerContainerClient(TestCase):
    """Test the DockerContainerClient implementation"""

    def setUp(self):
        """Set up test fixtures"""
        # Create a mock client that doesn't inherit from docker.DockerClient
        self.client = Mock(spec=DockerContainerClient)

        # Set up the methods we need to test
        self.client.get_runtime_type = DockerContainerClient.get_runtime_type.__get__(self.client)
        self.client.is_docker = DockerContainerClient.is_docker.__get__(self.client)
        self.client.is_finch = DockerContainerClient.is_finch.__get__(self.client)
        self.client.is_available = DockerContainerClient.is_available.__get__(self.client)
        self.client.load_image_from_archive = DockerContainerClient.load_image_from_archive.__get__(self.client)
        self.client.is_dockerfile_error = DockerContainerClient.is_dockerfile_error.__get__(self.client)
        self.client.list_containers_by_image = DockerContainerClient.list_containers_by_image.__get__(self.client)

        self.client.remove_image_safely = DockerContainerClient.remove_image_safely.__get__(self.client)
        self.client.validate_image_count = DockerContainerClient.validate_image_count.__get__(self.client)
        self.client.get_archive = DockerContainerClient.get_archive.__get__(self.client)

        # Set up the mocked docker client attributes
        self.client.api = Mock()
        self.client.images = Mock()
        self.client.containers = Mock()
        self.client.ping = Mock(return_value=True)

    def test_get_runtime_type(self):
        """Test that DockerContainerClient returns 'docker' as runtime type"""
        self.assertEqual(self.client.get_runtime_type(), "docker")

    def test_is_docker_returns_true(self):
        """Test that is_docker() returns True for DockerContainerClient"""
        self.assertTrue(self.client.is_docker())

    def test_is_finch_returns_false(self):
        """Test that is_finch() returns False for DockerContainerClient"""
        self.assertFalse(self.client.is_finch())

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

    def test_load_image_from_archive_multiple_images_error(self):
        """Test error when archive contains multiple images"""
        mock_image1 = Mock()
        mock_image2 = Mock()
        self.client.images.load.return_value = [mock_image1, mock_image2]

        mock_archive = Mock()

        with self.assertRaises(ContainerArchiveImageLoadFailedException) as context:
            self.client.load_image_from_archive(mock_archive)

        self.assertIn("single image", str(context.exception))

    def test_load_image_from_archive_empty_archive_error(self):
        """Test error when archive contains no images"""
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

    def test_remove_image_safely_success(self):
        """Test successful image removal"""
        self.client.remove_image_safely("test-image", force=True)
        self.client.images.remove.assert_called_once_with("test-image", force=True)

    def test_remove_image_safely_with_default_force(self):
        """Test image removal with default force parameter"""
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
            # Test cases: (image_count, range_tuple, expected_result)
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

    @patch("samcli.local.docker.container_client.DockerContainerClient.__init__", return_value=None)
    def test_from_existing_client(self, mock_init):
        """Test creating DockerContainerClient from existing client"""
        existing_client = Mock()
        existing_client.api = Mock()
        existing_client.api.base_url = "unix://var/run/docker.sock"
        existing_client.api._version = "1.41"

        result = DockerContainerClient.from_existing_client(existing_client)

        self.assertIsInstance(result, DockerContainerClient)
        mock_init.assert_called_once_with(base_url="unix://var/run/docker.sock", version="1.41")


class TestFinchContainerClient(TestCase):
    """Test the FinchContainerClient implementation"""

    def setUp(self):
        """Set up test fixtures"""
        # Create a mock client that doesn't inherit from docker.DockerClient
        self.client = Mock(spec=FinchContainerClient)

        # Set up the methods we need to test
        self.client.get_runtime_type = FinchContainerClient.get_runtime_type.__get__(self.client)
        self.client.is_docker = FinchContainerClient.is_docker.__get__(self.client)
        self.client.is_finch = FinchContainerClient.is_finch.__get__(self.client)
        self.client.load_image_from_archive = FinchContainerClient.load_image_from_archive.__get__(self.client)
        self.client.is_dockerfile_error = FinchContainerClient.is_dockerfile_error.__get__(self.client)
        self.client.list_containers_by_image = FinchContainerClient.list_containers_by_image.__get__(self.client)

        self.client.remove_image_safely = FinchContainerClient.remove_image_safely.__get__(self.client)
        self.client.validate_image_count = FinchContainerClient.validate_image_count.__get__(self.client)
        self.client._load_with_raw_api = FinchContainerClient._load_with_raw_api.__get__(self.client)
        self.client.get_archive = FinchContainerClient.get_archive.__get__(self.client)

        self.client._get_archive_from_mount = FinchContainerClient._get_archive_from_mount.__get__(self.client)

        # Set up the mocked docker client attributes
        self.client.api = Mock()
        self.client.images = Mock()
        self.client.containers = Mock()
        self.client.ping = Mock(return_value=True)

    def test_get_runtime_type(self):
        """Test that FinchContainerClient returns 'finch' as runtime type"""
        self.assertEqual(self.client.get_runtime_type(), "finch")

    def test_is_finch_returns_true(self):
        """Test that is_finch() returns True for FinchContainerClient"""
        self.assertTrue(self.client.is_finch())

    def test_is_docker_returns_false(self):
        """Test that is_docker() returns False for FinchContainerClient"""
        self.assertFalse(self.client.is_docker())

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
        # Mock containers with different images
        container1 = Mock()
        container1.image.tags = ["test-image:latest", "test-image:v1.0"]
        container1.image.id = "sha256:abc123"

        container2 = Mock()
        container2.image.tags = ["other-image:latest"]
        container2.image.id = "sha256:def456"

        container3 = Mock()
        container3.image.tags = ["test-image:v2.0"]
        container3.image.id = "sha256:ghi789"

        self.client.containers.list.return_value = [container1, container2, container3]

        result = self.client.list_containers_by_image("test-image", all_containers=True)

        # Should return containers 1 and 3 (both have test-image in tags)
        self.assertEqual(len(result), 2)
        self.assertIn(container1, result)
        self.assertIn(container3, result)
        self.assertNotIn(container2, result)

    def test_list_containers_by_image_success_by_id(self):
        """Test listing containers by image ID"""
        container1 = Mock()
        container1.image.tags = ["other-image:latest"]
        container1.image.id = "sha256:abc123"

        self.client.containers.list.return_value = [container1]

        result = self.client.list_containers_by_image("abc123", all_containers=True)

        self.assertEqual(len(result), 1)
        self.assertIn(container1, result)

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
        # Mock running container using the image
        container = Mock()
        container.status = "running"
        container.id = "container1"

        # Mock list_containers_by_image to return this container
        with patch.object(self.client, "list_containers_by_image", return_value=[container]):
            self.client.remove_image_safely("test-image", force=True)

        # Verify container was stopped and removed
        container.stop.assert_called_once()
        container.remove.assert_called_once_with(force=True)

        # Verify image was removed
        self.client.images.remove.assert_called_once_with("test-image", force=True)

    @patch("samcli.local.docker.container_client.LOG")
    def test_remove_image_safely_with_exited_containers(self, mock_log):
        """Test image removal with exited container cleanup"""
        # Mock exited container using the image
        container = Mock()
        container.status = "exited"
        container.id = "container2"

        # Mock list_containers_by_image to return this container
        with patch.object(self.client, "list_containers_by_image", return_value=[container]):
            self.client.remove_image_safely("test-image", force=True)

        # Verify container was removed but not stopped (already exited)
        container.stop.assert_not_called()
        container.remove.assert_called_once_with(force=True)

        # Verify image was removed
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
            # Test cases: (image_count, range_tuple, expected_result)
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

    def test_get_archive_finch_mount_fallback_no_artifacts(self):
        """Test get_archive mount fallback when artifacts don't exist on host"""
        container_id = "test-container-id"
        path = "/tmp/samcli/artifacts"

        # Mock container that fails get_archive
        mock_container = Mock()
        mock_container.get_archive.side_effect = Exception("mount-snapshot error")
        mock_container.attrs = {
            "Mounts": [{"Type": "bind", "Source": "/host/tmp/samcli", "Destination": "/tmp/samcli"}]
        }
        self.client.containers.get.return_value = mock_container

        # Mock os.path.exists to return False
        with patch("os.path.exists", return_value=False):
            with self.assertRaises(RuntimeError) as context:
                self.client.get_archive(container_id, path)

            self.assertIn("Could not find artifacts in Finch mounts", str(context.exception))

    def test_get_archive_finch_mount_fallback_no_samcli_mount(self):
        """Test get_archive mount fallback when no samcli mount is found"""
        container_id = "test-container-id"
        path = "/tmp/samcli/artifacts"

        # Mock container with no samcli mounts
        mock_container = Mock()
        mock_container.get_archive.side_effect = Exception("mount-snapshot error")
        mock_container.attrs = {"Mounts": [{"Type": "bind", "Source": "/host/other", "Destination": "/other"}]}
        self.client.containers.get.return_value = mock_container

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

    @patch("samcli.local.docker.container_client.FinchContainerClient.__init__", return_value=None)
    def test_from_existing_client(self, mock_init):
        """Test creating FinchContainerClient from existing client"""
        existing_client = Mock()
        existing_client.api = Mock()
        existing_client.api.base_url = "unix://var/run/finch.sock"
        existing_client.api._version = "1.41"

        result = FinchContainerClient.from_existing_client(existing_client)

        self.assertIsInstance(result, FinchContainerClient)
        mock_init.assert_called_once_with(base_url="unix://var/run/finch.sock", version="1.41")

    @patch("samcli.local.docker.container_client.FinchContainerClient.__init__", return_value=None)
    def test_from_existing_client_no_api(self, mock_init):
        """Test creating FinchContainerClient from existing client without API"""
        existing_client = Mock()
        del existing_client.api

        result = FinchContainerClient.from_existing_client(existing_client)

        self.assertIsInstance(result, FinchContainerClient)
        mock_init.assert_called_once_with(base_url=None, version=None)


class TestFinchContainerClientInit(TestCase):
    """Test the FinchContainerClient __init__ method"""

    @patch("samcli.local.docker.container_client_factory.ContainerClientFactory")
    @patch("samcli.local.docker.container_client.docker.DockerClient.__init__")
    def test_init_with_base_url_provided(self, mock_docker_init, mock_factory):
        """Test FinchContainerClient init when base_url is provided"""
        mock_docker_init.return_value = None

        # When base_url is provided, should not call factory
        client = FinchContainerClient(base_url="unix://test.sock")

        mock_factory._get_finch_socket_path.assert_not_called()
        mock_docker_init.assert_called_once_with(base_url="unix://test.sock")

    @patch("samcli.local.docker.container_client_factory.ContainerClientFactory")
    @patch("samcli.local.docker.container_client.docker.DockerClient.__init__")
    def test_init_without_base_url_with_socket_path(self, mock_docker_init, mock_factory):
        """Test FinchContainerClient init without base_url but with socket path from factory"""
        mock_docker_init.return_value = None
        mock_factory._get_finch_socket_path.return_value = "unix://finch.sock"

        client = FinchContainerClient()

        mock_factory._get_finch_socket_path.assert_called_once()
        mock_docker_init.assert_called_once_with(base_url="unix://finch.sock")

    @patch("samcli.local.docker.container_client_factory.ContainerClientFactory")
    @patch("samcli.local.docker.container_client.docker.DockerClient.__init__")
    def test_init_without_base_url_no_socket_path(self, mock_docker_init, mock_factory):
        """Test FinchContainerClient init without base_url and no socket path from factory"""
        mock_docker_init.return_value = None
        mock_factory._get_finch_socket_path.return_value = None

        client = FinchContainerClient()

        mock_factory._get_finch_socket_path.assert_called_once()
        mock_docker_init.assert_called_once_with()


class TestContainerClientBaseClass(TestCase):
    """Test the ContainerClient base class methods"""

    def setUp(self):
        """Set up test fixtures"""
        # Create a mock client that doesn't inherit from docker.DockerClient
        self.client = Mock(spec=ContainerClient)

        # Set up the methods we need to test
        self.client.from_existing_client = ContainerClient.from_existing_client.__get__(self.client)
        self.client.is_available = ContainerClient.is_available.__get__(self.client)
        self.client.is_finch = ContainerClient.is_finch.__get__(self.client)
        self.client.is_docker = ContainerClient.is_docker.__get__(self.client)

        # Set up the mocked docker client attributes
        self.client.ping = Mock(return_value=True)
        self.client.get_runtime_type = Mock(return_value="docker")

    def test_from_existing_client_with_api_attributes(self):
        """Test creating client from existing client with API attributes"""
        existing_client = Mock()
        existing_client.api = Mock()
        existing_client.api.base_url = "unix://var/run/docker.sock"
        existing_client.api._version = "1.41"

        # Test the logic by using DockerContainerClient instead of abstract ContainerClient
        result = DockerContainerClient.from_existing_client(existing_client)
        self.assertIsInstance(result, DockerContainerClient)

    @patch("samcli.local.docker.container_client.docker.DockerClient.__init__", return_value=None)
    def test_from_existing_client_without_api_attributes(self, mock_init):
        """Test creating client from existing client without API attributes"""
        existing_client = Mock()
        # Remove api attribute
        del existing_client.api

        # Test the logic by using DockerContainerClient instead of abstract ContainerClient
        result = DockerContainerClient.from_existing_client(existing_client)
        self.assertIsInstance(result, DockerContainerClient)
        mock_init.assert_called_once_with(base_url=None, version=None)

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

    def test_is_finch_when_runtime_is_finch(self):
        """Test is_finch returns True when runtime type is finch"""
        self.client.get_runtime_type.return_value = "finch"
        self.assertTrue(self.client.is_finch())

    def test_is_finch_when_runtime_is_not_finch(self):
        """Test is_finch returns False when runtime type is not finch"""
        self.client.get_runtime_type.return_value = "docker"
        self.assertFalse(self.client.is_finch())

    def test_is_docker_when_runtime_is_docker(self):
        """Test is_docker returns True when runtime type is docker"""
        self.client.get_runtime_type.return_value = "docker"
        self.assertTrue(self.client.is_docker())

    def test_is_docker_when_runtime_is_not_docker(self):
        """Test is_docker returns False when runtime type is not docker"""
        self.client.get_runtime_type.return_value = "finch"
        self.assertFalse(self.client.is_docker())


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


class TestContainerClientIntegrationScenarios(TestCase):
    """Test integration scenarios that simulate real-world usage"""

    def setUp(self):
        """Set up test fixtures"""
        self.docker_client = Mock(spec=DockerContainerClient)
        self.finch_client = Mock(spec=FinchContainerClient)

        # Set up methods for both clients
        for client_class, client_instance in [
            (DockerContainerClient, self.docker_client),
            (FinchContainerClient, self.finch_client),
        ]:
            client_instance.get_runtime_type = client_class.get_runtime_type.__get__(client_instance)
            client_instance.is_docker = client_class.is_docker.__get__(client_instance)
            client_instance.is_finch = client_class.is_finch.__get__(client_instance)
            client_instance.load_image_from_archive = client_class.load_image_from_archive.__get__(client_instance)
            client_instance.list_containers_by_image = client_class.list_containers_by_image.__get__(client_instance)
            client_instance.remove_image_safely = client_class.remove_image_safely.__get__(client_instance)

            # Set up mocked attributes
            client_instance.api = Mock()
            client_instance.images = Mock()
            client_instance.containers = Mock()

        # Set up Finch-specific methods
        self.finch_client._load_with_raw_api = FinchContainerClient._load_with_raw_api.__get__(self.finch_client)

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
        container1 = Mock()
        container1.image.tags = ["sam-build-image:latest"]
        container2 = Mock()
        container2.image.tags = ["other-image:latest"]

        self.finch_client.containers.list.return_value = [container1, container2]
        result = self.finch_client.list_containers_by_image("sam-build-image")

        # Should only return matching container
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0], container1)

    def test_cleanup_workflow_comparison(self):
        """Test cleanup workflow differences between Docker and Finch"""
        # Docker: simple cleanup
        self.docker_client.remove_image_safely("test-image")
        self.docker_client.images.remove.assert_called_once_with("test-image", force=True)

        # Finch: cleanup with container dependency handling
        container = Mock()
        container.status = "running"

        with patch.object(self.finch_client, "list_containers_by_image", return_value=[container]):
            self.finch_client.remove_image_safely("test-image")

        # Should stop and remove container first, then image
        container.stop.assert_called_once()
        container.remove.assert_called_once_with(force=True)
        self.finch_client.images.remove.assert_called_once_with("test-image", force=True)
