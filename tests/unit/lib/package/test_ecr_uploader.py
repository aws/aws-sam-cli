from unittest import TestCase
from unittest.mock import MagicMock, patch

from botocore.exceptions import ClientError
from docker.errors import APIError, BuildError
from parameterized import parameterized

from samcli.commands.package.exceptions import DockerLoginFailedError, DockerPushFailedError, ECRAuthorizationError
from samcli.lib.package.ecr_uploader import ECRUploader
from samcli.lib.utils.stream_writer import StreamWriter


class TestECRUploader(TestCase):
    def setUp(self):
        self.ecr_client = MagicMock()
        self.ecr_repo = "mock-image-repo"
        self.tag = "mock-tag"
        self.stream = "stream"
        self.docker_client = MagicMock()
        self.auth_config = {}
        self.error_args = {
            BuildError.__name__: {"reason": "mock_reason", "build_log": "mock_build_log"},
            APIError.__name__: {"message": "mock message"},
        }

    def test_ecr_uploader_init(self):
        ecr_uploader = ECRUploader(
            docker_client=self.docker_client, ecr_client=self.ecr_client, ecr_repo=self.ecr_repo, tag=self.tag
        )

        self.assertEqual(ecr_uploader.docker_client, self.docker_client)
        self.assertEqual(ecr_uploader.ecr_repo, self.ecr_repo)
        self.assertEqual(ecr_uploader.tag, self.tag)
        self.assertEqual(ecr_uploader.ecr_client, self.ecr_client)
        self.assertIsInstance(ecr_uploader.stream, StreamWriter)

    def test_ecr_login_failure(self):
        self.ecr_client.get_authorization_token = MagicMock(
            side_effect=ClientError(
                error_response={"Error": {"Message": "mock token error"}}, operation_name="get_authorization_token"
            )
        )
        ecr_uploader = ECRUploader(
            docker_client=self.docker_client, ecr_client=self.ecr_client, ecr_repo=self.ecr_repo, tag=self.tag
        )

        with self.assertRaises(ECRAuthorizationError):
            ecr_uploader.login()

    @patch("samcli.lib.package.ecr_uploader.base64")
    def test_docker_login_failure(self, base64_mock):
        base64_mock.b64decode.return_value = b"username:password"
        self.docker_client.login = MagicMock(side_effect=APIError(message="mock error"))
        self.ecr_client.get_authorization_token.return_value = {
            "authorizationData": [{"authorizationToken": "auth_token", "proxyEndpoint": "proxy"}]
        }
        ecr_uploader = ECRUploader(
            docker_client=self.docker_client, ecr_client=self.ecr_client, ecr_repo=self.ecr_repo, tag=self.tag
        )

        with self.assertRaises(DockerLoginFailedError):
            ecr_uploader.login()

    @patch("samcli.lib.package.ecr_uploader.base64")
    def test_login_success(self, base64_mock):
        base64_mock.b64decode.return_value = b"username:password"

        self.ecr_client.get_authorization_token.return_value = {
            "authorizationData": [{"authorizationToken": "auth_token", "proxyEndpoint": "proxy"}]
        }
        ecr_uploader = ECRUploader(
            docker_client=self.docker_client, ecr_client=self.ecr_client, ecr_repo=self.ecr_repo, tag=self.tag
        )

        ecr_uploader.login()

    @parameterized.expand([(BuildError,), (APIError,)])
    def test_upload_failure(self, error):
        image = "myimage:v1"
        ecr_uploader = ECRUploader(
            docker_client=self.docker_client, ecr_client=self.ecr_client, ecr_repo=self.ecr_repo, tag=self.tag
        )

        ecr_uploader.login = MagicMock()
        self.docker_client.images = MagicMock()
        self.docker_client.images.get = MagicMock(side_effect=error(**self.error_args.get(error.__name__)))

        with self.assertRaises(DockerPushFailedError):
            ecr_uploader.upload(image)

    def test_upload_success(self):
        image = "myimage:v1"
        self.docker_client.api.push.return_value.__iter__.return_value = iter(
            [
                {"status": "Pushing to xyz"},
                {"id": "1", "status": "Preparing", "progress": ""},
                {"id": "2", "status": "Preparing", "progress": ""},
                {"id": "3", "status": "Preparing", "progress": ""},
                {"id": "1", "status": "Pushing", "progress": "[====>   ]"},
                {"id": "3", "status": "Pushing", "progress": "[====>   ]"},
                {"id": "2", "status": "Pushing", "progress": "[====>   ]"},
                {"id": "3", "status": "Pushed", "progress": "[========>]"},
                {"id": "1", "status": "Pushed", "progress": "[========>]"},
                {"id": "2", "status": "Pushed", "progress": "[========>]"},
                {"status": f"image {image} pushed digest: a89q34f"},
                {},
            ]
        )

        ecr_uploader = ECRUploader(
            docker_client=self.docker_client, ecr_client=self.ecr_client, ecr_repo=self.ecr_repo, tag=self.tag
        )

        ecr_uploader.login = MagicMock()

        ecr_uploader.upload(image)

    def test_upload_failure_while_streaming(self):
        image = "myimage:v1"
        self.docker_client.api.push.return_value.__iter__.return_value = iter(
            [
                {"status": "Pushing to xyz"},
                {"id": "1", "status": "Preparing", "progress": ""},
                {"id": "2", "status": "Preparing", "progress": ""},
                {"id": "3", "status": "Preparing", "progress": ""},
                {"id": "1", "status": "Pushing", "progress": "[====>   ]"},
                {"id": "3", "status": "Pushing", "progress": "[====>   ]"},
                {"error": "Network Error!"},
                {},
            ]
        )

        ecr_uploader = ECRUploader(
            docker_client=self.docker_client, ecr_client=self.ecr_client, ecr_repo=self.ecr_repo, tag=self.tag
        )

        ecr_uploader.login = MagicMock()
        with self.assertRaises(DockerPushFailedError):
            ecr_uploader.upload(image)
