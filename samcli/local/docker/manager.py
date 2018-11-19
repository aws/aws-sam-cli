"""
Provides classes that interface with Docker to create, execute and manage containers.
"""

import logging
import re
import sys
import requests
import docker
from samcli.commands.exceptions import UserException

LOG = logging.getLogger(__name__)


class ContainerManager(object):
    """
    This class knows how to interface with Docker to create, execute and manage the container's life cycle. It can
    run multiple containers in parallel, and also comes with the ability to reuse existing containers in order to
    serve requests faster. It is also thread-safe.
    """

    _CONTAINER_NAME_PATTERN = '[a-zA-Z0-9][a-zA-Z0-9_.-]+'
    _container_name_regex = re.compile(_CONTAINER_NAME_PATTERN)

    def __init__(self,
                 docker_client=None,
                 docker_network_id=None,
                 skip_pull_image=False):
        """
        Instantiate the container manager

        :param docker_network_id: Optional Docker network to run this container in.
        :param docker_client: Optional docker client object
        :param bool skip_pull_image: Should we pull new Docker container image?
        """

        self.skip_pull_image = skip_pull_image
        self.docker_network_id = docker_network_id
        self.docker_client = docker_client or docker.from_env()

    @staticmethod
    def is_valid_container_name(name):
        """
        Checks if a given name is a valid Docker container name

        Parameters
        ----------
        name str
            Docker container name to check

        Returns
        -------
        bool
            True, if name is a valid Docker container name, False otherwise
        """

        return True if ContainerManager._container_name_regex.match(name) else False

    @property
    def is_docker_reachable(self):
        """
        Checks if Docker daemon is running. This is required for us to invoke the function locally

        Returns
        -------
        bool
            True, if Docker is available, False otherwise
        """

        try:
            self.docker_client.ping()
            return True

        # When Docker is not installed, a request.exceptions.ConnectionError is thrown.
        except (docker.errors.APIError, requests.exceptions.ConnectionError):
            return False

    def is_container_name_taken(self, name):
        """
        Checks if a given name is taken by another Docker container

        Parameters
        ----------
        name str
            Docker container name to check

        Returns
        -------
        bool
            True, if name is already taken by another Docker container, False otherwise
        """

        containers = self.docker_client.containers.list(all=True, filters={"name": name})

        return len(containers) > 0

    def run(self, container, input_data=None, warm=False):
        """
        Create and run a Docker container based on the given configuration.

        :param samcli.local.docker.container.Container container: Container to create and run
        :param input_data: Optional. Input data sent to the container through container's stdin.
        :param bool warm: Indicates if an existing container can be reused. Defaults False ie. a new container will
            be created for every request.
        :raises DockerImagePullFailedException: If the Docker image was not available in the server
        """

        if warm:
            raise ValueError("The facility to invoke warm container does not exist")

        image_name = container.image

        is_image_local = self.has_image(image_name)

        if not is_image_local or not self.skip_pull_image:
            try:
                self.pull_image(image_name)
            except DockerImagePullFailedException:
                if not is_image_local:
                    raise DockerImagePullFailedException(
                        "Could not find {} image locally and failed to pull it from docker.".format(image_name))

                LOG.info(
                    "Failed to download a new %s image. Invoking with the already downloaded image.", image_name)
        else:
            LOG.info("Requested to skip pulling images ...\n")

        try:
            if not container.is_created():
                # Create the container first before running.
                # Create the container in appropriate Docker network
                container.network_id = self.docker_network_id
                container.create()

            container.start(input_data=input_data)
        except docker.errors.APIError as api_error:
            if api_error.status_code == 409:
                raise DockerContainerException("'{}' Docker container name is already taken".format(container.name))
            if api_error.is_server_error():
                raise DockerContainerException("Something went wrong on the Docker server")
            raise

    def stop(self, container):
        """
        Stop and delete the container

        :param samcli.local.docker.container.Container container: Container to stop
        """
        container.delete()

    def pull_image(self, image_name, stream=None):
        """
        Ask Docker to pull the container image with given name.

        :param string image_name: Name of the image
        :param stream: Optional stream to write output to. Defaults to stderr
        :raises DockerImagePullFailedException: If the Docker image was not available in the server
        """
        stream = stream or sys.stderr
        try:
            result_itr = self.docker_client.api.pull(image_name, stream=True, decode=True)
        except docker.errors.APIError as ex:
            LOG.debug("Failed to download image with name %s", image_name)
            raise DockerImagePullFailedException(str(ex))

        # io streams, especially StringIO, work only with unicode strings
        stream.write(u"\nFetching {} Docker container image...".format(image_name))

        # Each line contains information on progress of the pull. Each line is a JSON string
        for _ in result_itr:
            # For every line, print a dot to show progress
            stream.write(u'.')
            stream.flush()

        # We are done. Go to the next line
        stream.write(u"\n")

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


class DockerContainerException(UserException):
    """
    Something went wrong during Docker container creation
    """
    pass
