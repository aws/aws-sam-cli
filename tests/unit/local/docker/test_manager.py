"""
Tests container manager
"""

import io

from unittest import TestCase
import requests
from mock import PropertyMock, Mock, patch
from docker.errors import ImageNotFound, APIError

from samcli.local.docker.manager import (
    ContainerManager, DockerContainerException, DockerImagePullFailedException)

from parameterized import parameterized


class TestContainerManager_init(TestCase):

    def test_must_initialize_with_default_value(self):

        manager = ContainerManager()
        self.assertFalse(manager.skip_pull_image)
        self.assertIsNone(manager.docker_network_id)


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

    def test_must_error_with_warm(self):

        with self.assertRaises(ValueError):
            self.manager.run(self.container_mock, warm=True)

    def test_must_pull_image_and_run_container(self):
        input_data = "input data"

        self.manager.has_image = Mock()
        self.manager.pull_image = Mock()

        # Assume the image doesn't exist.
        self.manager.has_image.return_value = False

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

        self.manager.run(self.container_mock, input_data)

        self.manager.has_image.assert_called_with(self.image_name)
        self.manager.pull_image.assert_called_with(self.image_name)
        self.container_mock.start.assert_called_with(input_data=input_data)

    def test_must_not_pull_image_if_asked_to_skip(self):
        input_data = "input data"

        self.manager.has_image = Mock()
        self.manager.pull_image = Mock()

        # Assume the image exist.
        self.manager.has_image.return_value = True
        # And, skip pulling
        self.manager.skip_pull_image = True

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

    @parameterized.expand([
        ("Create raises error", "create"),
        ("Start raises error", "start")
    ])
    @patch("docker.errors.APIError.status_code", new_callable=PropertyMock)
    def test_must_raise_DockerContainerException_if_container_raises_conflict_error(
            self, test_name, failing_method, status_code_mock):
        conflict_api_error = APIError("conflict")

        status_code_mock.return_value = 409
        conflict_api_error.is_server_error = Mock(return_value=False)

        self.manager.has_image = Mock()
        self.manager.pull_image = Mock()

        self.manager.has_image.return_value = False

        self.container_mock.is_created.return_value = False

        with patch.object(self.container_mock, failing_method, create=True) as failing_method_mock:
            failing_method_mock.side_effect = conflict_api_error
            with self.assertRaises(DockerContainerException):
                self.manager.run(self.container_mock)

    @parameterized.expand([
        ("Create raises error", "create"),
        ("Start raises error", "start")
    ])
    @patch("docker.errors.APIError.status_code", new_callable=PropertyMock)
    def test_must_raise_DockerContainerException_if_container_raises_server_error(
            self, test_name, failing_method, status_code_mock):
        conflict_api_error = APIError("server error")

        status_code_mock.return_value = 500
        conflict_api_error.is_server_error = Mock(return_value=True)

        self.manager.has_image = Mock()
        self.manager.pull_image = Mock()

        self.manager.has_image.return_value = False

        self.container_mock.is_created.return_value = False

        with patch.object(self.container_mock, failing_method, create=True) as failing_method_mock:
            failing_method_mock.side_effect = conflict_api_error
            with self.assertRaises(DockerContainerException):
                self.manager.run(self.container_mock)

    @parameterized.expand([
        ("Create raises error", "create"),
        ("Start raises error", "start")
    ])
    @patch("docker.errors.APIError.status_code", new_callable=PropertyMock)
    def test_must_bubble_error_if_container_raises_unhandled_error(
            self, test_name, failing_method, status_code_mock):
        conflict_api_error = APIError("unhandled")

        status_code_mock.return_value = 400
        conflict_api_error.is_server_error = Mock(return_value=False)

        self.manager.has_image = Mock()
        self.manager.pull_image = Mock()

        self.manager.has_image.return_value = False

        self.container_mock.is_created.return_value = False

        with patch.object(self.container_mock, failing_method, create=True) as failing_method_mock:
            failing_method_mock.side_effect = conflict_api_error
            with self.assertRaises(APIError):
                self.manager.run(self.container_mock)


class TestContainerManager_is_valid_container_name(TestCase):

    @parameterized.expand([
        ("containername"),
        ("container_name"),
        ("container.name"),
        ("container-name")
    ])
    def test_must_identify_valid_name(self, container_name):
        self.assertTrue(ContainerManager.is_valid_container_name(container_name))

    @parameterized.expand([
        ("Wrong length", "n"),
        ("Invalid as first character _", "_container-name"),
        ("Invalid as first character .", ".container-name"),
        ("Invalid as first character -", "-container-name"),
        ("Invalid name", "c*nt@!ner~n@^^e"),
    ])
    def test_must_identify_invalid_name(self, test_name, container_name):
        self.assertFalse(ContainerManager.is_valid_container_name(container_name))


class TestContainerManager_is_docker_reachable(TestCase):

    def setUp(self):
        self.ping_mock = Mock()

        docker_client_mock = Mock()
        docker_client_mock.ping = self.ping_mock

        self.manager = ContainerManager(docker_client=docker_client_mock)

    def test_must_use_docker_client_ping(self):
        self.manager.is_docker_reachable()

        self.ping_mock.assert_called_once_with()

    def test_must_return_true_if_ping_does_not_raise(self):
        is_connected = self.manager.is_docker_reachable()

        self.assertTrue(is_connected)

    def test_must_return_false_if_ping_raises_APIError(self):
        self.ping_mock.side_effect = APIError("error")

        is_connected = self.manager.is_docker_reachable()

        self.assertFalse(is_connected)

    def test_must_return_false_if_ping_raises_ConnectionError(self):
        self.ping_mock.side_effect = requests.exceptions.ConnectionError("error")

        is_connected = self.manager.is_docker_reachable()

        self.assertFalse(is_connected)


class TestContainerManager_is_container_name_taken(TestCase):

    def setUp(self):
        self.containers_list_mock = Mock()

        docker_client_mock = Mock()
        docker_client_mock.containers.list = self.containers_list_mock

        self.manager = ContainerManager(docker_client=docker_client_mock)

    def test_must_use_docker_client_list_with_filter(self):
        container_name = "container-name"

        self.containers_list_mock.return_value = []

        self.manager.is_container_name_taken(container_name)

        self.containers_list_mock.assert_called_once_with(
            all=True, filters={"name": container_name}
        )

    def test_must_return_false_if_no_container_with_this_name_exists(self):
        container_name = "container-name"

        self.containers_list_mock.return_value = []

        is_name_taken = self.manager.is_container_name_taken(container_name)

        self.assertFalse(is_name_taken)

    def test_must_return_true_if_any_container_with_this_name_exists(self):
        container_name = "container_name"

        self.containers_list_mock.return_value = [
            Mock(),
        ]

        is_name_taken = self.manager.is_container_name_taken(container_name)

        self.assertTrue(is_name_taken)


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
            self.image_name,
            '.' * len(pull_result)  # Progress bar will print one dot per response from pull API
        )

        self.manager.pull_image(self.image_name, stream=stream)

        self.mock_docker_client.api.pull.assert_called_with(self.image_name,
                                                            stream=True,
                                                            decode=True)
        self.assertEquals(stream.getvalue(), expected_stream_output)

    def test_must_raise_if_image_not_found(self):
        msg = "some error"
        self.mock_docker_client.api.pull.side_effect = APIError(msg)

        with self.assertRaises(DockerImagePullFailedException) as context:
            self.manager.pull_image("imagename")

        ex = context.exception
        self.assertEquals(str(ex), msg)


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
