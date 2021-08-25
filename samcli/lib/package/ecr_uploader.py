"""
Client for uploading packaged artifacts to ecr
"""
import logging
import base64
import os

from typing import Dict
import click
import botocore
import docker

from docker.errors import BuildError, APIError

from samcli.commands.package.exceptions import (
    DockerPushFailedError,
    DockerLoginFailedError,
    ECRAuthorizationError,
    DeleteArtifactFailedError,
)
from samcli.lib.package.image_utils import tag_translation
from samcli.lib.package.stream_cursor_utils import cursor_up, cursor_left, cursor_down, clear_line
from samcli.lib.utils.osutils import stderr
from samcli.lib.utils.stream_writer import StreamWriter

LOG = logging.getLogger(__name__)

ECR_USERNAME = "AWS"


class ECRUploader:
    """
    Class to upload Images to ECR.
    """

    def __init__(self, docker_client, ecr_client, ecr_repo, ecr_repo_multi, tag="latest", stream=stderr()):
        self.docker_client = docker_client if docker_client else docker.from_env()
        self.ecr_client = ecr_client
        self.ecr_repo = ecr_repo
        self.ecr_repo_multi = ecr_repo_multi
        self.tag = tag
        self.auth_config = {}
        self.stream = StreamWriter(stream=stream, auto_flush=True)
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
        try:
            docker_img = self.docker_client.images.get(image)

            _tag = tag_translation(image, docker_image_id=docker_img.id, gen_tag=self.tag)
            repository = (
                self.ecr_repo if not isinstance(self.ecr_repo_multi, dict) else self.ecr_repo_multi.get(resource_name)
            )

            docker_img.tag(repository=repository, tag=_tag)
            push_logs = self.docker_client.api.push(
                repository=repository, tag=_tag, auth_config=self.auth_config, stream=True, decode=True
            )
            self._stream_progress(push_logs)

        except (BuildError, APIError) as ex:
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

    # TODO: move this to a generic class to allow for streaming logs back from docker.
    def _stream_progress(self, logs):
        """
        Stream progress from docker push logs and move the cursor based on the log id.
        :param logs: generator from docker_clent.api.push
        """
        ids = dict()
        for log in logs:
            _id = log.get("id", None)
            status = log.get("status", None)
            progress = log.get("progress", "")
            error = log.get("error", "")
            change_cursor_count = 0
            if _id:
                try:
                    curr_log_line_id = ids[_id]
                    change_cursor_count = len(ids) - curr_log_line_id
                    self.stream.write((cursor_up(change_cursor_count) + cursor_left).encode())
                except KeyError:
                    ids[_id] = len(ids)
            else:
                ids = dict()

            self._stream_write(_id, status, progress, error)

            if _id:
                self.stream.write((cursor_down(change_cursor_count) + cursor_left).encode())
        self.stream.write(os.linesep.encode())

    def _stream_write(self, _id, status, progress, error):
        """
        Write stream information to stderr, if the stream information contains a log id,
        use the carraige return character to rewrite that particular line.
        :param _id: docker log id
        :param status: docker log status
        :param progress: docker log progress
        :param error: docker log error
        """
        if error:
            raise DockerPushFailedError(msg=error)
        if not status:
            return

        # NOTE(sriram-mv): Required for the purposes of when the cursor overflows existing terminal buffer.
        self.stream.write(os.linesep.encode())
        self.stream.write((cursor_up() + cursor_left).encode())
        self.stream.write(clear_line().encode())

        if not _id:
            self.stream.write(f"{status}{os.linesep}".encode())
        else:
            self.stream.write(f"\r{_id}: {status} {progress}".encode())
