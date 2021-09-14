from unittest import TestCase
from unittest.mock import MagicMock, patch, call

from botocore.exceptions import ClientError
from docker.errors import APIError, BuildError
from parameterized import parameterized

# import click
from samcli.commands.package.exceptions import (
    DockerLoginFailedError,
    DockerPushFailedError,
    ECRAuthorizationError,
    ImageNotFoundError,
    DeleteArtifactFailedError,
)
from samcli.lib.package.ecr_uploader import ECRUploader
from samcli.lib.utils.stream_writer import StreamWriter


class TestECRUploader(TestCase):
    def setUp(self):
        self.ecr_client = MagicMock()
        self.ecr_repo = "mock-image-repo"
        self.ecr_repo_multi = {"HelloWorldFunction": "mock-image-repo"}
        self.tag = "mock-tag"
        self.stream = "stream"
        self.docker_client = MagicMock()
        self.auth_config = {}
        self.error_args = {
            BuildError.__name__: {"reason": "mock_reason", "build_log": "mock_build_log"},
            APIError.__name__: {"message": "mock message"},
        }
        self.image_uri = "900643008914.dkr.ecr.us-east-1.amazonaws.com/" + self.ecr_repo + ":" + self.tag
        self.property_name = "AWS::Serverless::Function"
        self.resource_id = "HelloWorldFunction"

    def test_ecr_uploader_init(self):
        ecr_uploader = ECRUploader(
            docker_client=self.docker_client,
            ecr_client=self.ecr_client,
            ecr_repo=self.ecr_repo,
            ecr_repo_multi=self.ecr_repo_multi,
            tag=self.tag,
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
            docker_client=self.docker_client,
            ecr_client=self.ecr_client,
            ecr_repo=self.ecr_repo,
            ecr_repo_multi=self.ecr_repo_multi,
            tag=self.tag,
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
            docker_client=self.docker_client,
            ecr_client=self.ecr_client,
            ecr_repo=self.ecr_repo,
            ecr_repo_multi=self.ecr_repo_multi,
            tag=self.tag,
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
            docker_client=self.docker_client,
            ecr_client=self.ecr_client,
            ecr_repo=self.ecr_repo,
            ecr_repo_multi=self.ecr_repo_multi,
            tag=self.tag,
        )

        ecr_uploader.login()

    @patch("samcli.lib.package.ecr_uploader.base64")
    def test_directly_upload_login_success(self, base64_mock):
        base64_mock.b64decode.return_value = b"username:password"

        self.ecr_client.get_authorization_token.return_value = {
            "authorizationData": [{"authorizationToken": "auth_token", "proxyEndpoint": "proxy"}]
        }
        ecr_uploader = ECRUploader(
            docker_client=self.docker_client,
            ecr_client=self.ecr_client,
            ecr_repo=self.ecr_repo,
            ecr_repo_multi=self.ecr_repo_multi,
            tag=self.tag,
        )

        ecr_uploader.upload("myimage:v1", "Myresource")

    @parameterized.expand([(BuildError,), (APIError,)])
    def test_upload_failure(self, error):
        image = "myimage:v1"
        ecr_uploader = ECRUploader(
            docker_client=self.docker_client,
            ecr_client=self.ecr_client,
            ecr_repo=self.ecr_repo,
            ecr_repo_multi=self.ecr_repo_multi,
            tag=self.tag,
        )

        ecr_uploader.login = MagicMock()
        self.docker_client.images = MagicMock()
        self.docker_client.images.get = MagicMock(side_effect=error(**self.error_args.get(error.__name__)))

        with self.assertRaises(DockerPushFailedError):
            ecr_uploader.upload(image, resource_name="HelloWorldFunction")

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
            docker_client=self.docker_client,
            ecr_client=self.ecr_client,
            ecr_repo=self.ecr_repo,
            ecr_repo_multi=self.ecr_repo_multi,
            tag=self.tag,
        )

        ecr_uploader.login = MagicMock()

        ecr_uploader.upload(image, resource_name="HelloWorldFunction")

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
            docker_client=self.docker_client,
            ecr_client=self.ecr_client,
            ecr_repo=self.ecr_repo,
            ecr_repo_multi=self.ecr_repo_multi,
            tag=self.tag,
        )

        ecr_uploader.login = MagicMock()
        with self.assertRaises(DockerPushFailedError):
            ecr_uploader.upload(image, resource_name="HelloWorldFunction")

    @patch("samcli.lib.package.ecr_uploader.click.echo")
    def test_delete_artifact_successful(self, patched_click_echo):
        ecr_uploader = ECRUploader(
            docker_client=self.docker_client,
            ecr_client=self.ecr_client,
            ecr_repo=self.ecr_repo,
            ecr_repo_multi=self.ecr_repo_multi,
            tag=self.tag,
        )
        ecr_uploader.ecr_client.batch_delete_image.return_value = {
            "imageIds": [
                {"imageTag": self.tag},
            ],
            "failures": [],
        }

        ecr_uploader.delete_artifact(
            image_uri=self.image_uri, resource_id=self.resource_id, property_name=self.property_name
        )

        expected_click_echo_calls = [
            call(f"\t- Deleting ECR image {self.tag} in repository {self.ecr_repo}"),
        ]
        self.assertEqual(expected_click_echo_calls, patched_click_echo.call_args_list)

    @patch("samcli.lib.package.ecr_uploader.click.echo")
    def test_delete_artifact_no_image_found(self, patched_click_echo):
        ecr_uploader = ECRUploader(
            docker_client=self.docker_client,
            ecr_client=self.ecr_client,
            ecr_repo=self.ecr_repo,
            ecr_repo_multi=self.ecr_repo_multi,
            tag=self.tag,
        )
        ecr_uploader.ecr_client.batch_delete_image.return_value = {
            "failures": [{"imageId": {"imageTag": self.tag}, "failureCode": "ImageNotFound"}]
        }

        ecr_uploader.delete_artifact(
            image_uri=self.image_uri, resource_id=self.resource_id, property_name=self.property_name
        )

        expected_click_echo_calls = [
            call(f"\t- Could not find image with tag {self.tag} in repository mock-image-repo"),
        ]
        self.assertEqual(expected_click_echo_calls, patched_click_echo.call_args_list)

    @patch("samcli.lib.package.ecr_uploader.click.echo")
    def test_delete_artifact_resp_failure(self, patched_click_echo):
        ecr_uploader = ECRUploader(
            docker_client=self.docker_client,
            ecr_client=self.ecr_client,
            ecr_repo=self.ecr_repo,
            ecr_repo_multi=self.ecr_repo_multi,
            tag=self.tag,
        )
        ecr_uploader.ecr_client.batch_delete_image.return_value = {
            "failures": [
                {
                    "imageId": {"imageTag": self.tag},
                    "failureCode": "Mock response Failure",
                    "failureReason": "Mock ECR testing",
                }
            ]
        }

        ecr_uploader.delete_artifact(
            image_uri=self.image_uri, resource_id=self.resource_id, property_name=self.property_name
        )

        expected_click_echo_calls = [
            call(f"\t- Could not delete image with tag {self.tag} in repository mock-image-repo"),
        ]
        self.assertEqual(expected_click_echo_calls, patched_click_echo.call_args_list)

    def test_delete_artifact_client_error(self):
        ecr_uploader = ECRUploader(
            docker_client=self.docker_client,
            ecr_client=self.ecr_client,
            ecr_repo=self.ecr_repo,
            ecr_repo_multi=self.ecr_repo_multi,
            tag=self.tag,
        )
        ecr_uploader.ecr_client.batch_delete_image = MagicMock(
            side_effect=ClientError(
                error_response={"Error": {"Message": "mock client error"}}, operation_name="batch_delete_image"
            )
        )

        with self.assertRaises(DeleteArtifactFailedError):
            ecr_uploader.delete_artifact(
                image_uri=self.image_uri, resource_id=self.resource_id, property_name=self.property_name
            )

    @patch("samcli.lib.package.ecr_uploader.click.echo")
    def test_delete_ecr_repository(self, patched_click_echo):
        ecr_uploader = ECRUploader(
            docker_client=self.docker_client,
            ecr_client=self.ecr_client,
            ecr_repo=self.ecr_repo,
            ecr_repo_multi=self.ecr_repo_multi,
            tag=self.tag,
        )
        ecr_uploader.ecr_client.delete_repository = MagicMock()

        ecr_uploader.delete_ecr_repository(physical_id=self.ecr_repo)

        expected_click_echo_calls = [
            call(f"\t- Deleting ECR repository {self.ecr_repo}"),
        ]
        self.assertEqual(expected_click_echo_calls, patched_click_echo.call_args_list)

    def test_parse_image_url(self):

        valid = [
            {"url": self.image_uri, "result": {"repository": "mock-image-repo", "image_tag": "mock-tag"}},
            {"url": "mock-image-rep:mock-tag", "result": {"repository": "mock-image-rep", "image_tag": "mock-tag"}},
            {
                "url": "mock-image-repo",
                "result": {"repository": "mock-image-repo", "image_tag": "latest"},
            },
        ]

        for config in valid:
            result = ECRUploader.parse_image_url(image_uri=config["url"])

            self.assertEqual(result, config["result"])
