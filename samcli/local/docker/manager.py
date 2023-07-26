"""
Provides classes that interface with Docker to create, execute and manage containers.
"""

import logging
import sys
import threading

import docker

from samcli.lib.constants import DOCKER_MIN_API_VERSION
from samcli.lib.utils.stream_writer import StreamWriter
from samcli.local.docker import utils
from samcli.local.docker.container import Container
from samcli.local.docker.lambda_image import LambdaImage

LOG = logging.getLogger(__name__)


class ContainerManager:
    """
    This class knows how to interface with Docker to create, execute and manage the container's life cycle. It can
    run multiple containers in parallel, and also comes with the ability to reuse existing containers in order to
    serve requests faster. It is also thread-safe.
    """

    def __init__(self, docker_network_id=None, docker_client=None, skip_pull_image=False, do_shutdown_event=False):
        """
        Instantiate the container manager

        :param docker_network_id: Optional Docker network to run this container in.
        :param docker_client: Optional docker client object
        :param bool skip_pull_image: Should we pull new Docker container image?
        :param bool do_shutdown_event: Optional. If True, send a SHUTDOWN event to the container before final teardown.
        """

        self.skip_pull_image = skip_pull_image
        self.docker_network_id = docker_network_id
        self.docker_client = docker_client or docker.from_env(version=DOCKER_MIN_API_VERSION)
        self.do_shutdown_event = do_shutdown_event

        self._lock = threading.Lock()
        self._lock_per_image = {}

    @property
    def is_docker_reachable(self):
        """
        Checks if Docker daemon is running. This is required for us to invoke the function locally

        Returns
        -------
        bool
            True, if Docker is available, False otherwise
        """
        return utils.is_docker_reachable(self.docker_client)

    def create(self, container):
        """
        Create a container based on the given configuration.

        Parameters
        ----------
        container samcli.local.docker.container.Container:
            Container to be created

        Raises
        ------
        DockerImagePullFailedException
            If the Docker image was not available in the server
        """
        image_name = container.image

        is_image_local = self.has_image(image_name)

        # Skip Pulling a new image if:
        # a) Image is available AND we are asked to skip pulling the image
        # OR b) Image name is samcli/lambda
        # OR c) Image is available AND image name ends with "rapid-${SAM_CLI_VERSION}"
        if is_image_local and self.skip_pull_image:
            LOG.info("Requested to skip pulling images ...\n")
        elif image_name.startswith("samcli/lambda") or (is_image_local and LambdaImage.is_rapid_image(image_name)):
            LOG.info("Using local image: %s.\n", image_name)
        else:
            try:
                self.pull_image(image_name)
            except DockerImagePullFailedException as ex:
                if not is_image_local:
                    raise DockerImagePullFailedException(
                        "Could not find {} image locally and failed to pull it from docker.".format(image_name)
                    ) from ex

                LOG.info("Failed to download a new %s image. Invoking with the already downloaded image.", image_name)

        container.network_id = self.docker_network_id
        container.create()

    def run(self, container, input_data=None):
        """
        Run a Docker container based on the given configuration.
        If the container is not created, it will call Create method to create.

        Parameters
        ----------
        container: samcli.local.docker.container.Container
            Container to create and run
        input_data: str, optional
            Input data sent to the container through container's stdin.

        Raises
        ------
        DockerImagePullFailedException
            If the Docker image was not available in the server
        """
        if not container.is_created():
            self.create(container)

        container.start(input_data=input_data)

    def stop(self, container: Container) -> None:
        """
        Stop and delete the container

        :param samcli.local.docker.container.Container container: Container to stop
        """
        if self.do_shutdown_event:
            container.stop()
        container.delete()

    def pull_image(self, image_name, tag=None, stream=None):
        """
        Ask Docker to pull the container image with given name.

        Parameters
        ----------
        image_name str
            Name of the image
        stream samcli.lib.utils.stream_writer.StreamWriter
            Optional stream writer to output to. Defaults to stderr

        Raises
        ------
        DockerImagePullFailedException
            If the Docker image was not available in the server
        """
        if tag is None:
            _image_name_split = image_name.split(":")
            # Separate the image_name from the tag so less forgiving docker clones
            # (podman) get the image name as the URL they expect. Official docker seems
            # to clean this up internally.
            tag = _image_name_split[1] if len(_image_name_split) > 1 else "latest"
            image_name = _image_name_split[0]
        # use a global lock to get the image lock
        with self._lock:
            image_lock = self._lock_per_image.get(image_name)
            if not image_lock:
                image_lock = threading.Lock()
                self._lock_per_image[image_name] = image_lock

        # with specific image lock, pull this image only once
        # since there are different locks for each image, different images can be pulled in parallel
        with image_lock:
            stream_writer = stream or StreamWriter(sys.stderr)

            try:
                result_itr = self.docker_client.api.pull(image_name, tag=tag, stream=True, decode=True)
            except docker.errors.APIError as ex:
                LOG.debug("Failed to download image with name %s", image_name)
                raise DockerImagePullFailedException(str(ex)) from ex

            # io streams, especially StringIO, work only with unicode strings
            stream_writer.write("\nFetching {}:{} Docker container image...".format(image_name, tag))

            # Each line contains information on progress of the pull. Each line is a JSON string
            for _ in result_itr:
                # For every line, print a dot to show progress
                stream_writer.write(".")
                stream_writer.flush()

            # We are done. Go to the next line
            stream_writer.write("\n")

    def has_image(self, image_name):
        """
        Is the container image with given name available?

        :param string image_name: Name of the image
        :return bool: True, if image is available. False, otherwise
        """

        try:
            self.docker_client.images.get(image_name)
            return True
        except docker.errors.ImageNotFound:
            return False


class DockerImagePullFailedException(Exception):
    pass
