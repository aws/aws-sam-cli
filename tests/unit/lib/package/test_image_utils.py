from unittest import TestCase
from unittest.mock import MagicMock, patch

from docker.errors import APIError, NullResource

from samcli.commands.package.exceptions import DockerGetLocalImageFailedError
from samcli.lib.package.image_utils import tag_translation, NonLocalImageException, NoImageFoundException


class TestImageUtils(TestCase):
    def test_tag_translation_with_image_id(self):
        local_image = "helloworld:v1"
        self.assertEqual("helloworld-1234-v1", tag_translation(local_image, docker_image_id="sha256:1234"))

    def test_tag_translation_with_image_id_and_no_tag(self):
        local_image = "helloworld"
        self.assertEqual("helloworld-1234-latest", tag_translation(local_image, docker_image_id="sha256:1234"))

    @patch("samcli.lib.package.image_utils.docker")
    def test_tag_translation_without_image_id(self, mock_docker):
        mock_docker_client = MagicMock()
        mock_docker_id = MagicMock(id="sha256:1234")
        mock_docker_client.images.get.return_value = mock_docker_id
        mock_docker.from_env = mock_docker_client
        local_image = "helloworld:v1"
        self.assertEqual("helloworld-1234-v1", tag_translation(local_image, docker_image_id="sha256:1234"))

    @patch("samcli.lib.package.image_utils.docker")
    def test_tag_translation_docker_error_without_image_id(self, mock_docker):
        mock_docker.from_env = MagicMock(side_effect=APIError("mock error"))
        local_image = "helloworld:v1"
        with self.assertRaises(DockerGetLocalImageFailedError):
            tag_translation(local_image)

    @patch("samcli.lib.package.image_utils.docker")
    def test_tag_translation_docker_error_non_existent_image_id(self, mock_docker):
        mock_docker.from_env = MagicMock(side_effect=NullResource("mock error"))
        local_image = None
        with self.assertRaises(NoImageFoundException):
            tag_translation(local_image)

    def test_tag_translation_for_ecr_image(self):
        non_local_image = "123456789012.dkr.ecr.us-east-1.amazonaws.com/myrepo"
        with self.assertRaises(NonLocalImageException):
            tag_translation(non_local_image)
