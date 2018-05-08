"""
Tests container manager
"""

import io

from unittest import TestCase
from mock import Mock
from docker.errors import ImageNotFound
from samcli.local.docker.manager import ContainerManager, DockerImageNotFoundException


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
        self.mock_docker_client.api.pull.side_effect = ImageNotFound(msg)

        with self.assertRaises(DockerImageNotFoundException) as context:
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
