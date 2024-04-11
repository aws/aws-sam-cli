"""
Client for uploading packaged artifacts to ecr
"""

import base64
import logging
from io import StringIO
from pathlib import Path
from typing import Dict

import botocore
import click
import docker
from docker.errors import APIError, BuildError

from samcli.commands.package.exceptions import (
    DeleteArtifactFailedError,
    DockerLoginFailedError,
    DockerPushFailedError,
    ECRAuthorizationError,
)
from samcli.lib.constants import DOCKER_MIN_API_VERSION
from samcli.lib.docker.log_streamer import LogStreamer, LogStreamError
from samcli.lib.package.image_utils import tag_translation
from samcli.lib.utils.osutils import stderr
from samcli.lib.utils.stream_writer import StreamWriter

LOG = logging.getLogger(__name__)

ECR_USERNAME = "AWS"


class ECRUploader:
    """
    Class to upload Images to ECR.
    """

    def __init__(
        self, docker_client, ecr_client, ecr_repo, ecr_repo_multi, no_progressbar=False, tag="latest", stream=stderr()
    ):
        self.docker_client = docker_client if docker_client else docker.from_env(version=DOCKER_MIN_API_VERSION)
        self.ecr_client = ecr_client
        self.ecr_repo = ecr_repo
        self.ecr_repo_multi = ecr_repo_multi
        self.tag = tag
        self.auth_config = {}
        self.no_progressbar = no_progressbar
        self.stream = StreamWriter(stream=stream, auto_flush=True)
        self.log_streamer = LogStreamer(stream=self.stream)
        self.login_session_active = False

    def login(self):
        """
        Logs into the supplied ECR with credentials.
        """
        try:
            token = self.ecr_client.get_authorization_token()
        except botocore.exceptions.ClientError as ex:
            raise ECRAuthorizationError(msg=ex.response["Error"]["Message"]) from ex

        username, password = base64.b64decode(token["authorizationData"][0]["authorizationToken"]).decode().split(":")
        registry = token["authorizationData"][0]["proxyEndpoint"]

        try:
            self.docker_client.login(username=ECR_USERNAME, password=password, registry=registry)
        except APIError as ex:
            raise DockerLoginFailedError(msg=str(ex)) from ex
        self.auth_config = {"username": username, "password": password}

    def upload(self, image, resource_name):
        """
        Uploads given local image to ECR.
        :param image: locally tagged docker image that would be uploaded to ECR.
        :param resource_name: logical ID of the resource to be uploaded to ECR.
        :return: remote ECR image path that has been uploaded.
        """
        if not self.login_session_active:
            self.login()
            self.login_session_active = True

        # Sometimes the `resource_name` is used as the `image` parameter to `tag_translation`.
        # This is because these two cases (directly from an archive or by ID) are effectively
        # anonymous, so the best identifier available in scope is the resource name.
        try:
            if Path(image).is_file():
                with open(image, mode="rb") as image_archive:
                    [docker_img, *rest] = self.docker_client.images.load(image_archive)
                    if len(rest) != 0:
                        raise DockerPushFailedError("Archive must represent a single image")
                    _tag = tag_translation(resource_name, docker_image_id=docker_img.id, gen_tag=self.tag)
            else:
                # If it's not a file, it's gotta be a {repo}:{tag} or a sha256:{digest}
                docker_img = self.docker_client.images.get(image)
                _tag = tag_translation(
                    resource_name if image == docker_img.id else image,
                    docker_image_id=docker_img.id,
                    gen_tag=self.tag,
                )

            repository = (
                self.ecr_repo
                if not self.ecr_repo_multi or not isinstance(self.ecr_repo_multi, dict)
                else self.ecr_repo_multi.get(resource_name)
            )

            docker_img.tag(repository=repository, tag=_tag)
            push_logs = self.docker_client.api.push(
                repository=repository, tag=_tag, auth_config=self.auth_config, stream=True, decode=True
            )
            if not self.no_progressbar:
                self.log_streamer.stream_progress(push_logs)
            else:
                # we need to wait till the image got pushed to ecr, without this workaround sam sync for template
                # contains image always fail, because the provided ecr uri is not exist.
                _log_streamer = LogStreamer(stream=StreamWriter(stream=StringIO(), auto_flush=True))
                _log_streamer.stream_progress(push_logs)

        except (BuildError, APIError, LogStreamError) as ex:
            raise DockerPushFailedError(msg=str(ex)) from ex

        return f"{repository}:{_tag}"

    def delete_artifact(self, image_uri: str, resource_id: str, property_name: str):
        """
        Delete the given ECR image by extracting the repository and image_tag from
        image_uri

        :param image_uri: image_uri of the image to be deleted
        :param resource_id: id of the resource for which the image is deleted
        :param property_name: provided property_name for the resource
        """
        try:
            repo_image_tag = self.parse_image_url(image_uri=image_uri)
            repository = repo_image_tag["repository"]
            image_tag = repo_image_tag["image_tag"]
            resp = self.ecr_client.batch_delete_image(
                repositoryName=repository,
                imageIds=[
                    {"imageTag": image_tag},
                ],
            )
            if resp["failures"]:
                # Image not found
                image_details = resp["failures"][0]
                if image_details["failureCode"] == "ImageNotFound":
                    LOG.debug(
                        "Could not delete image for %s parameter of %s resource as it does not exist. \n",
                        property_name,
                        resource_id,
                    )
                    click.echo(f"\t- Could not find image with tag {image_tag} in repository {repository}")
                else:
                    LOG.debug(
                        "Could not delete the image for the resource %s. FailureCode: %s, FailureReason: %s",
                        property_name,
                        image_details["failureCode"],
                        image_details["failureReason"],
                    )
                    click.echo(f"\t- Could not delete image with tag {image_tag} in repository {repository}")
            else:
                LOG.debug("Deleting ECR image with tag %s", image_tag)
                click.echo(f"\t- Deleting ECR image {image_tag} in repository {repository}")

        except botocore.exceptions.ClientError as ex:
            # Handle Client errors such as RepositoryNotFoundException or InvalidParameterException
            if "RepositoryNotFoundException" not in str(ex):
                LOG.debug("DeleteArtifactFailedError Exception : %s", str(ex))
                raise DeleteArtifactFailedError(resource_id=resource_id, property_name=property_name, ex=ex) from ex
            LOG.debug("RepositoryNotFoundException : %s", str(ex))

    def delete_ecr_repository(self, physical_id: str):
        """
        Delete ECR repository using the physical_id

        :param: physical_id of the repository to be deleted
        """
        try:
            click.echo(f"\t- Deleting ECR repository {physical_id}")
            self.ecr_client.delete_repository(repositoryName=physical_id, force=True)
        except self.ecr_client.exceptions.RepositoryNotFoundException:
            # If the repository is empty, cloudformation automatically deletes
            # the repository when cf_client.delete_stack is called.
            LOG.debug("Could not find repository %s", physical_id)

    @staticmethod
    def parse_image_url(image_uri: str) -> Dict:
        result = {}
        registry_repo_tag = image_uri.split("/", 1)
        repo_colon_image_tag = None
        if len(registry_repo_tag) == 1:
            # If there is no registry specified, e.g. repo:tag
            repo_colon_image_tag = registry_repo_tag[0]
        else:
            # Registry present, e.g. registry/repo:tag
            repo_colon_image_tag = registry_repo_tag[1]
        repo_image_tag_split = repo_colon_image_tag.split(":")

        # If no tag is specified, use latest
        result["repository"] = repo_image_tag_split[0]
        result["image_tag"] = repo_image_tag_split[1] if len(repo_image_tag_split) > 1 else "latest"

        return result
