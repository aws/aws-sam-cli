"""
Tests container manager
"""

import importlib
import os
from unittest import TestCase
from unittest.mock import Mock, patch, MagicMock, ANY, call, PropertyMock

import requests
from docker.errors import APIError, ImageNotFound

import docker

from samcli.local.docker.manager import ContainerManager, DockerImagePullFailedException
from samcli.local.docker.container import ContainerContext
from samcli.local.docker.lambda_image import RAPID_IMAGE_TAG_PREFIX

# Note: Individual tests will mock admin_container_preference as needed
# instead of using a global patch to avoid test interference


# pywintypes is not available non-Windows OS,
# we need to make up an Exception for this
class MockPywintypesError(Exception):
    pass


def patched_modules():
    # Mock these modules to simulate a Windows environment
    platform_mock = Mock()
    platform_mock.system.return_value = "Windows"
    pywintypes_mock = Mock()
    pywintypes_mock.error = MockPywintypesError
    return {
        "platform": platform_mock,
        "pywintypes": pywintypes_mock,
    }


class TestContainerManager_runtime_failures(TestCase):
    @patch("samcli.local.docker.container_client_factory.ContainerClientFactory.create_client")
    def setUp(self, mock_get_client):
        self.mock_client = Mock()
        mock_get_client.return_value = self.mock_client
        self.manager = ContainerManager()

    def test_create_fails_on_connection_error(self):
        """Test create method fails when connection error occurs"""
        mock_container = Mock()
        mock_context = Mock()

        mock_container.create.side_effect = requests.exceptions.ConnectionError("Connection failed")

        with self.assertRaises(requests.exceptions.ConnectionError):
            self.manager.create(mock_container, mock_context)

    def test_create_fails_on_api_error(self):
        """Test create method fails when Docker API error occurs"""
        mock_container = Mock()
        mock_context = Mock()

        mock_container.create.side_effect = docker.errors.APIError("API error")

        with self.assertRaises(docker.errors.APIError):
            self.manager.create(mock_container, mock_context)

    def test_has_image_fails_on_connection_error(self):
        """Test has_image method fails when connection error occurs"""
        self.manager.container_client.images.get.side_effect = requests.exceptions.ConnectionError("Connection failed")

        with self.assertRaises(requests.exceptions.ConnectionError):
            self.manager.has_image("test-image")

    def test_has_image_returns_false_on_image_not_found(self):
        """Test has_image returns False when image not found"""
        self.manager.container_client.images.get.side_effect = docker.errors.ImageNotFound("Image not found")

        result = self.manager.has_image("test-image")

        self.assertFalse(result)

    def test_pull_image_fails_on_connection_error(self):
        """Test pull_image method fails when connection error occurs"""
        self.manager.container_client.api.pull.side_effect = requests.exceptions.ConnectionError("Connection failed")

        with self.assertRaises(requests.exceptions.ConnectionError):
            self.manager.pull_image("test-image")

    def test_connection_refused_error_propagates(self):
        """Test that ConnectionRefusedError propagates without retry"""
        mock_container = Mock()
        mock_context = Mock()

        mock_container.create.side_effect = ConnectionRefusedError("Connection refused")

        with self.assertRaises(ConnectionRefusedError):
            self.manager.create(mock_container, mock_context)


class TestContainerManager_init(TestCase):
    @patch("samcli.local.docker.container_client_factory.ContainerClientFactory.create_client")
    def test_must_initialize_with_default_value(self, mock_get_client):
        mock_get_client.return_value = Mock()
        manager = ContainerManager()
        self.assertFalse(manager.skip_pull_image)


class TestContainerManager_admin_detection(TestCase):
    def setUp(self):
        self.mock_docker_client = Mock()

    @patch("samcli.local.docker.utils.LOG")
    @patch("samcli.local.docker.container_client_factory.ContainerClientFactory.create_client")
    @patch.dict(os.environ, {}, clear=True)
    def test_init_sets_finch_socket_for_admin_device_with_finch_available(self, mock_get_client, mock_log):
        # Mock the client validation to set DOCKER_HOST (simulating Finch setup)
        def mock_validation():
            os.environ["DOCKER_HOST"] = "unix://finch.sock"
            # Simulate the log call that would happen in get_validated_container_client
            mock_log.debug("Administrator container preference detected. Using Finch as Container Engine.")
            return Mock()

        mock_get_client.side_effect = mock_validation
        ContainerManager()

        self.assertEqual(os.environ.get("DOCKER_HOST"), "unix://finch.sock")
        # Verify log message for administrator preference Finch usage
        mock_log.debug.assert_called_with(
            "Administrator container preference detected. Using Finch as Container Engine."
        )

    @patch("samcli.local.docker.container_client_factory.ContainerClientFactory.get_admin_container_preference")
    @patch("samcli.local.docker.container_client_factory.ContainerClientFactory.create_client")
    def test_init_does_not_set_finch_socket_for_non_admin_device(self, mock_get_client, mock_admin_pref):
        mock_get_client.return_value = Mock()
        mock_admin_pref.return_value = None

        with patch.dict(os.environ, {}, clear=True):
            ContainerManager()
            self.assertNotIn("DOCKER_HOST", os.environ)


class TestContainerManager_run(TestCase):
    @patch("samcli.local.docker.container_client_factory.ContainerClientFactory.create_client")
    def setUp(self, mock_get_client):
        self.mock_docker_client = Mock()
        mock_get_client.return_value = self.mock_docker_client
        with patch(
            "samcli.local.docker.container_client_factory.ContainerClientFactory.get_admin_container_preference",
            return_value=None,
        ):
            self.manager = ContainerManager()

        self.image_name = "image name"
        self.container_mock = Mock()
        self.container_mock.image = self.image_name
        self.container_mock.start = Mock()
        self.container_mock.create = Mock()
        self.container_mock.is_created = Mock()

    def test_must_pull_image_and_run_container(self):
        input_data = "input data"
        context = ContainerContext.BUILD

        self.manager.has_image = Mock()
        self.manager.pull_image = Mock()

        # Assume the image doesn't exist.
        self.manager.has_image.return_value = False
        self.container_mock.is_created.return_value = False

        self.manager.run(self.container_mock, context, input_data)

        self.manager.has_image.assert_called_with(self.image_name)
        self.manager.pull_image.assert_called_with(self.image_name)
        self.container_mock.start.assert_called_with(input_data=input_data)

    def test_must_pull_image_if_image_exist_and_no_skip(self):
        input_data = "input data"
        context = ContainerContext.BUILD

        self.manager.has_image = Mock()
        self.manager.pull_image = Mock()

        # Assume the image exist.
        self.manager.has_image.return_value = True
        # And, don't skip pulling => Pull again
        self.manager.skip_pull_image = False
        self.container_mock.is_created.return_value = False

        self.manager.run(self.container_mock, context, input_data)

        self.manager.has_image.assert_called_with(self.image_name)
        self.manager.pull_image.assert_called_with(self.image_name)
        self.container_mock.start.assert_called_with(input_data=input_data)

    def test_must_not_pull_image_if_image_is_samcli_lambda_image(self):
        input_data = "input data"
        context = ContainerContext.BUILD

        self.manager.has_image = Mock()
        self.manager.pull_image = Mock()

        # Assume the image exist.
        self.manager.has_image.return_value = True
        # And, don't skip pulling => Pull again
        self.manager.skip_pull_image = False

        self.container_mock.image = "samcli/lambda"
        self.container_mock.is_created.return_value = False

        self.manager.run(self.container_mock, context, input_data)

        self.manager.has_image.assert_called_with("samcli/lambda")
        self.manager.pull_image.assert_not_called()
        self.container_mock.start.assert_called_with(input_data=input_data)

    def test_must_not_pull_image_if_image_is_rapid_image(self):
        input_data = "input data"
        context = ContainerContext.BUILD
        rapid_image_name = f"Mock_image_name/python:3.9-{RAPID_IMAGE_TAG_PREFIX}-x86_64"

        self.manager.has_image = Mock()
        self.manager.pull_image = Mock()

        # Assume the image exist.
        self.manager.has_image.return_value = True
        # And, don't skip pulling => Pull again
        self.manager.skip_pull_image = False

        self.container_mock.image = rapid_image_name
        self.container_mock.is_created.return_value = False

        self.manager.run(self.container_mock, context, input_data)

        self.manager.has_image.assert_called_with(rapid_image_name)
        self.manager.pull_image.assert_not_called()
        self.container_mock.start.assert_called_with(input_data=input_data)

    def test_must_not_pull_image_if_asked_to_skip(self):
        input_data = "input data"
        context = ContainerContext.BUILD

        self.manager.has_image = Mock()
        self.manager.pull_image = Mock()

        # Assume the image exist.
        self.manager.has_image.return_value = True
        # And, skip pulling
        self.manager.skip_pull_image = True
        self.container_mock.is_created.return_value = False

        self.manager.run(self.container_mock, context, input_data)

        self.manager.has_image.assert_called_with(self.image_name)
        # Must not call pull_image
        self.manager.pull_image.assert_not_called()
        self.container_mock.start.assert_called_with(input_data=input_data)

    def test_must_fail_if_image_pull_failed_and_image_does_not_exist(self):
        input_data = "input data"
        context = ContainerContext.BUILD

        self.manager.has_image = Mock()
        self.manager.pull_image = Mock(side_effect=DockerImagePullFailedException("Failed to pull image"))

        # Assume the image exist.
        self.manager.has_image.return_value = False
        # And, don't skip pulling => Pull again
        self.manager.skip_pull_image = False
        self.container_mock.is_created.return_value = False

        with self.assertRaises(DockerImagePullFailedException):
            self.manager.run(self.container_mock, context, input_data)

        self.manager.has_image.assert_called_with(self.image_name)
        self.manager.pull_image.assert_called_with(self.image_name)
        self.container_mock.start.assert_not_called()

    def test_must_run_if_image_pull_failed_and_image_does_exist(self):
        input_data = "input data"
        context = ContainerContext.BUILD

        self.manager.has_image = Mock()
        self.manager.pull_image = Mock(side_effect=DockerImagePullFailedException("Failed to pull image"))

        # Assume the image exist.
        self.manager.has_image.return_value = True
        # And, don't skip pulling => Pull again
        self.manager.skip_pull_image = False
        self.container_mock.is_created.return_value = False

        self.manager.run(self.container_mock, context, input_data)

        self.manager.has_image.assert_called_with(self.image_name)
        self.manager.pull_image.assert_called_with(self.image_name)
        self.container_mock.start.assert_called_with(input_data=input_data)

    def test_must_create_container_if_not_exists(self):
        input_data = "input data"
        context = ContainerContext.BUILD
        self.manager.has_image = Mock()
        self.manager.pull_image = Mock()

        # Assume container does NOT exist
        self.container_mock.is_created.return_value = False

        self.manager.run(self.container_mock, context, input_data)

        # Container should be created
        self.container_mock.create.assert_called_with(context)

    def test_must_not_create_container_if_it_already_exists(self):
        input_data = "input data"
        context = ContainerContext.BUILD
        self.manager.has_image = Mock()
        self.manager.pull_image = Mock()

        # Assume container does NOT exist
        self.container_mock.is_created.return_value = True

        self.manager.run(self.container_mock, context, input_data)

        # Container should be created
        self.container_mock.create.assert_not_called()


class TestContainerManager_pull_image(TestCase):
    @patch("samcli.local.docker.container_client_factory.ContainerClientFactory.create_client")
    def setUp(self, mock_get_client):
        self.image_name = "image name"

        self.mock_docker_client = Mock()
        self.mock_docker_client.api = Mock()
        self.mock_docker_client.api.pull = Mock()
        mock_get_client.return_value = self.mock_docker_client

        with patch(
            "samcli.local.docker.container_client_factory.ContainerClientFactory.get_admin_container_preference",
            return_value=None,
        ):
            self.manager = ContainerManager()

    def test_must_pull_and_print_progress_dots(self):
        stream = Mock()
        pull_result = [1, 2, 3, 4, 5, 6, 7, 8, 9, 0]
        self.mock_docker_client.api.pull.return_value = pull_result
        expected_stream_calls = [
            call(f"\nFetching {self.image_name}:latest Docker container image..."),
            call("."),
            call("."),
            call("."),
            call("."),
            call("."),
            call("."),
            call("."),
            call("."),
            call("."),
            call("."),
            call("\n"),
        ]

        self.manager.pull_image(self.image_name, stream=stream)

        self.mock_docker_client.api.pull.assert_called_with(self.image_name, stream=True, decode=True, tag="latest")

        stream.write_str.assert_has_calls(expected_stream_calls)

    def test_must_raise_if_image_not_found(self):
        msg = "some error"
        self.mock_docker_client.api.pull.side_effect = APIError(msg)

        with self.assertRaises(DockerImagePullFailedException) as context:
            self.manager.pull_image("imagename")

        ex = context.exception
        self.assertEqual(str(ex), msg)

    @patch("samcli.local.docker.manager.threading")
    def test_multiple_image_pulls_must_use_locks(self, mock_threading):
        self.mock_docker_client.api.pull.return_value = [1, 2, 3]

        # mock general lock
        mock_lock = MagicMock()
        self.manager._lock = mock_lock

        # mock locks per image
        mock_image1_lock = MagicMock()
        mock_image2_lock = MagicMock()
        mock_threading.Lock.side_effect = [mock_image1_lock, mock_image2_lock]

        # pull 2 different images for multiple times
        self.manager.pull_image("image1")
        self.manager.pull_image("image1")
        self.manager.pull_image("image2")

        # assert that image1 lock have been used twice and image2 lock only used once
        mock_image1_lock.assert_has_calls(2 * [call.__enter__(), call.__exit__(ANY, ANY, ANY)], any_order=True)
        mock_image2_lock.assert_has_calls([call.__enter__(), call.__exit__(ANY, ANY, ANY)])

        # assert that general lock have been used three times for all the image pulls
        mock_lock.assert_has_calls(3 * [call.__enter__(), call.__exit__(ANY, ANY, ANY)], any_order=True)


class TestContainerManager_has_image(TestCase):
    @patch("samcli.local.docker.container_client_factory.ContainerClientFactory.create_client")
    def setUp(self, mock_get_client):
        self.image_name = "image name"

        self.mock_docker_client = Mock()
        self.mock_docker_client.images = Mock()
        self.mock_docker_client.images.get = Mock()
        mock_get_client.return_value = self.mock_docker_client

        with patch(
            "samcli.local.docker.container_client_factory.ContainerClientFactory.get_admin_container_preference",
            return_value=None,
        ):
            self.manager = ContainerManager()

    def test_must_find_an_image(self):
        self.assertTrue(self.manager.has_image(self.image_name))

    def test_must_not_find_image(self):
        self.mock_docker_client.images.get.side_effect = ImageNotFound("test")
        self.assertFalse(self.manager.has_image(self.image_name))


class TestContainerManager_stop(TestCase):
    @patch("samcli.local.docker.container_client_factory.ContainerClientFactory.create_client")
    def test_must_call_delete_on_container(self, mock_create_client):
        with patch(
            "samcli.local.docker.container_client_factory.ContainerClientFactory.get_admin_container_preference",
            return_value=None,
        ):
            manager = ContainerManager()
        container = Mock()
        container.delete = Mock()

        manager.stop(container)
        container.delete.assert_called_with()


class TestContainerManager_inspect(TestCase):
    @patch("samcli.local.docker.container_client_factory.ContainerClientFactory.create_client")
    def test_must_call_inspect_on_container(self, mock_create_client):
        with patch(
            "samcli.local.docker.container_client_factory.ContainerClientFactory.get_admin_container_preference",
            return_value=None,
        ):
            manager = ContainerManager()
        manager.container_client = Mock()

        container = "container_id"

        manager.inspect(container)
        manager.container_client.docker_client.api.inspect_container(container)

    @patch("samcli.local.docker.container_client_factory.ContainerClientFactory.create_client")
    @patch("samcli.local.docker.manager.LOG")
    def test_must_fail_with_error_message(self, mock_log, mock_create_client):
        with patch(
            "samcli.local.docker.container_client_factory.ContainerClientFactory.get_admin_container_preference",
            return_value=None,
        ):
            manager = ContainerManager()
        manager.container_client.api.inspect_container = Mock()
        manager.container_client.api.inspect_container.side_effect = [docker.errors.APIError("Failed")]

        return_val = manager.inspect("container_id")

        self.assertEqual(return_val, False)
        mock_log.debug.assert_called_once_with("Failed to call Docker inspect: %s", "Failed")
