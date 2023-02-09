"""
Tests container manager
"""

import io
import importlib
from unittest import TestCase
from unittest.mock import Mock, patch, MagicMock, ANY, call

import requests
from docker.errors import APIError, ImageNotFound
from samcli.local.docker.manager import ContainerManager, DockerImagePullFailedException
from samcli.local.docker.lambda_image import RAPID_IMAGE_TAG_PREFIX


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


class TestContainerManager_init(TestCase):
    def test_must_initialize_with_default_value(self):

        manager = ContainerManager()
        self.assertFalse(manager.skip_pull_image)


class TestContainerManager_run(TestCase):
    def setUp(self):
        self.mock_docker_client = Mock()
        self.manager = ContainerManager(docker_client=self.mock_docker_client)

        self.image_name = "image name"
        self.container_mock = Mock()
        self.container_mock.image = self.image_name
        self.container_mock.start = Mock()
        self.container_mock.create = Mock()
        self.container_mock.is_created = Mock()

    def test_must_pull_image_and_run_container(self):
        input_data = "input data"

        self.manager.has_image = Mock()
        self.manager.pull_image = Mock()

        # Assume the image doesn't exist.
        self.manager.has_image.return_value = False
        self.container_mock.is_created.return_value = False

        self.manager.run(self.container_mock, input_data)

        self.manager.has_image.assert_called_with(self.image_name)
        self.manager.pull_image.assert_called_with(self.image_name)
        self.container_mock.start.assert_called_with(input_data=input_data)

    def test_must_pull_image_if_image_exist_and_no_skip(self):
        input_data = "input data"

        self.manager.has_image = Mock()
        self.manager.pull_image = Mock()

        # Assume the image exist.
        self.manager.has_image.return_value = True
        # And, don't skip pulling => Pull again
        self.manager.skip_pull_image = False
        self.container_mock.is_created.return_value = False

        self.manager.run(self.container_mock, input_data)

        self.manager.has_image.assert_called_with(self.image_name)
        self.manager.pull_image.assert_called_with(self.image_name)
        self.container_mock.start.assert_called_with(input_data=input_data)

    def test_must_not_pull_image_if_image_is_samcli_lambda_image(self):
        input_data = "input data"

        self.manager.has_image = Mock()
        self.manager.pull_image = Mock()

        # Assume the image exist.
        self.manager.has_image.return_value = True
        # And, don't skip pulling => Pull again
        self.manager.skip_pull_image = False

        self.container_mock.image = "samcli/lambda"
        self.container_mock.is_created.return_value = False

        self.manager.run(self.container_mock, input_data)

        self.manager.has_image.assert_called_with("samcli/lambda")
        self.manager.pull_image.assert_not_called()
        self.container_mock.start.assert_called_with(input_data=input_data)

    def test_must_not_pull_image_if_image_is_rapid_image(self):
        input_data = "input data"
        rapid_image_name = f"Mock_image_name/python:3.9-{RAPID_IMAGE_TAG_PREFIX}-x86_64"

        self.manager.has_image = Mock()
        self.manager.pull_image = Mock()

        # Assume the image exist.
        self.manager.has_image.return_value = True
        # And, don't skip pulling => Pull again
        self.manager.skip_pull_image = False

        self.container_mock.image = rapid_image_name
        self.container_mock.is_created.return_value = False

        self.manager.run(self.container_mock, input_data)

        self.manager.has_image.assert_called_with(rapid_image_name)
        self.manager.pull_image.assert_not_called()
        self.container_mock.start.assert_called_with(input_data=input_data)

    def test_must_not_pull_image_if_asked_to_skip(self):
        input_data = "input data"

        self.manager.has_image = Mock()
        self.manager.pull_image = Mock()

        # Assume the image exist.
        self.manager.has_image.return_value = True
        # And, skip pulling
        self.manager.skip_pull_image = True
        self.container_mock.is_created.return_value = False

        self.manager.run(self.container_mock, input_data)

        self.manager.has_image.assert_called_with(self.image_name)
        # Must not call pull_image
        self.manager.pull_image.assert_not_called()
        self.container_mock.start.assert_called_with(input_data=input_data)

    def test_must_fail_if_image_pull_failed_and_image_does_not_exist(self):
        input_data = "input data"

        self.manager.has_image = Mock()
        self.manager.pull_image = Mock(side_effect=DockerImagePullFailedException("Failed to pull image"))

        # Assume the image exist.
        self.manager.has_image.return_value = False
        # And, don't skip pulling => Pull again
        self.manager.skip_pull_image = False
        self.container_mock.is_created.return_value = False

        with self.assertRaises(DockerImagePullFailedException):
            self.manager.run(self.container_mock, input_data)

        self.manager.has_image.assert_called_with(self.image_name)
        self.manager.pull_image.assert_called_with(self.image_name)
        self.container_mock.start.assert_not_called()

    def test_must_run_if_image_pull_failed_and_image_does_exist(self):
        input_data = "input data"

        self.manager.has_image = Mock()
        self.manager.pull_image = Mock(side_effect=DockerImagePullFailedException("Failed to pull image"))

        # Assume the image exist.
        self.manager.has_image.return_value = True
        # And, don't skip pulling => Pull again
        self.manager.skip_pull_image = False
        self.container_mock.is_created.return_value = False

        self.manager.run(self.container_mock, input_data)

        self.manager.has_image.assert_called_with(self.image_name)
        self.manager.pull_image.assert_called_with(self.image_name)
        self.container_mock.start.assert_called_with(input_data=input_data)

    def test_must_create_container_if_not_exists(self):
        input_data = "input data"
        self.manager.has_image = Mock()
        self.manager.pull_image = Mock()

        # Assume container does NOT exist
        self.container_mock.is_created.return_value = False

        self.manager.run(self.container_mock, input_data)

        # Container should be created
        self.container_mock.create.assert_called_with()

    def test_must_not_create_container_if_it_already_exists(self):
        input_data = "input data"
        self.manager.has_image = Mock()
        self.manager.pull_image = Mock()

        # Assume container does NOT exist
        self.container_mock.is_created.return_value = True

        self.manager.run(self.container_mock, input_data)

        # Container should be created
        self.container_mock.create.assert_not_called()


class TestContainerManager_pull_image(TestCase):
    def setUp(self):
        self.image_name = "image name"

        self.mock_docker_client = Mock()
        self.mock_docker_client.api = Mock()
        self.mock_docker_client.api.pull = Mock()

        self.manager = ContainerManager(docker_client=self.mock_docker_client)

    def test_must_pull_and_print_progress_dots(self):

        stream = io.StringIO()
        pull_result = [1, 2, 3, 4, 5, 6, 7, 8, 9, 0]
        self.mock_docker_client.api.pull.return_value = pull_result
        expected_stream_output = "\nFetching {} Docker container image...{}\n".format(
            self.image_name, "." * len(pull_result)  # Progress bar will print one dot per response from pull API
        )

        self.manager.pull_image(self.image_name, stream=stream)

        self.mock_docker_client.api.pull.assert_called_with(self.image_name, stream=True, decode=True, tag="latest")
        self.assertEqual(stream.getvalue(), expected_stream_output)

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


class TestContainerManager_is_docker_reachable(TestCase):
    def setUp(self):
        self.ping_mock = Mock()

        self.docker_client_mock = Mock()
        self.docker_client_mock.ping = self.ping_mock

        self.manager = ContainerManager(docker_client=self.docker_client_mock)

    def test_must_use_docker_client_ping(self):
        with patch.dict("sys.modules", patched_modules()):
            import samcli.local.docker.manager as manager_module
            import samcli.local.docker.utils as docker_utils

            importlib.reload(manager_module)
            importlib.reload(docker_utils)
            self.manager.is_docker_reachable

            self.ping_mock.assert_called_once_with()

    def test_must_return_true_if_ping_does_not_raise(self):
        with patch.dict("sys.modules", patched_modules()):
            import samcli.local.docker.manager as manager_module
            import samcli.local.docker.utils as docker_utils

            importlib.reload(manager_module)
            importlib.reload(docker_utils)
            is_reachable = self.manager.is_docker_reachable

            self.assertTrue(is_reachable)

    def test_must_return_false_if_ping_raises_api_error(self):
        self.ping_mock.side_effect = APIError("error")

        is_reachable = self.manager.is_docker_reachable

        self.assertFalse(is_reachable)

    def test_must_return_false_if_ping_raises_connection_error(self):
        self.ping_mock.side_effect = requests.exceptions.ConnectionError("error")

        is_reachable = self.manager.is_docker_reachable

        self.assertFalse(is_reachable)

    def test_must_return_false_if_ping_raises_pywintypes_error(self):
        with patch.dict("sys.modules", patched_modules()):
            import samcli.local.docker.manager as manager_module
            import samcli.local.docker.utils as docker_utils

            importlib.reload(manager_module)
            importlib.reload(docker_utils)
            manager = manager_module.ContainerManager(docker_client=self.docker_client_mock)
            import pywintypes

            self.ping_mock.side_effect = pywintypes.error("pywintypes.error")
            is_reachable = manager.is_docker_reachable
            self.assertFalse(is_reachable)

        # reload modules to ensure platform.system() is unpatched
        importlib.reload(manager_module)

    def test_must_return_True_simulate_non_windows_platform(self):

        # Mock these modules to simulate a Windows environment
        platform_mock = Mock()
        platform_mock.system.return_value = "Darwin"
        modules = {
            "platform": platform_mock,
        }
        with patch.dict("sys.modules", modules):
            import samcli.local.docker.manager as manager_module

            importlib.reload(manager_module)
            manager = manager_module.ContainerManager(docker_client=self.docker_client_mock)

            is_reachable = manager.is_docker_reachable
            self.assertTrue(is_reachable)

        # reload modules to ensure platform.system() is unpatched
        importlib.reload(manager_module)


class TestContainerManager_has_image(TestCase):
    def setUp(self):
        self.image_name = "image name"

        self.mock_docker_client = Mock()
        self.mock_docker_client.images = Mock()
        self.mock_docker_client.images.get = Mock()

        self.manager = ContainerManager(docker_client=self.mock_docker_client)

    def test_must_find_an_image(self):

        self.assertTrue(self.manager.has_image(self.image_name))

    def test_must_not_find_image(self):

        self.mock_docker_client.images.get.side_effect = ImageNotFound("test")
        self.assertFalse(self.manager.has_image(self.image_name))


class TestContainerManager_stop(TestCase):
    def test_must_call_delete_on_container(self):

        manager = ContainerManager()
        container = Mock()
        container.delete = Mock()

        manager.stop(container)
        container.delete.assert_called_with()
