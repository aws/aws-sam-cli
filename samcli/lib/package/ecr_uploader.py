"""
Client for uploading packaged artifacts to ecr
"""
import logging
import base64
import os

import botocore
import docker

from docker.errors import BuildError, APIError

from samcli.commands.package.exceptions import DockerPushFailedError, DockerLoginFailedError, ECRAuthorizationError
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

    # TODO: move this to a generic class to allow for streaming logs back from docker.
    def _stream_progress(self, logs):
        """
        Stream progress from docker push logs and move the cursor based on the log id.
        :param logs: generator from docker_clent.api.push
        :return:
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
