"""
Provides classes that interface with Docker to create, execute and manage containers.
"""

import logging
import sys
import docker

LOG = logging.getLogger(__name__)


class ContainerManager(object):
    """
    This class knows how to interface with Docker to create, execute and manage the container's life cycle. It can
    run multiple containers in parallel, and also comes with the ability to reuse existing containers in order to
    serve requests faster. It is also thread-safe.
    """

    def __init__(self,
                 docker_network_id=None,
                 docker_client=None,
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

    def run(self, container, input_data=None, warm=False):
        """
        Create and run a Docker container based on the given configuration.

        :param samcli.local.docker.container.Container container: Container to create and run
        :param input_data: Optional. Input data sent to the container through container's stdin.
        :param bool warm: Indicates if an existing container can be reused. Defaults False ie. a new container will
            be created for every request.
        :raises DockerImageNotFoundException: If the Docker image was not available in the server
        """

        if warm:
            raise ValueError("The facility to invoke warm container does not exist")

        image_name = container.image

        # Pull a new image if: a) Image is not available OR b) We are not asked to skip pulling the image
        if not self.has_image(image_name) or not self.skip_pull_image:
            self.pull_image(image_name)
        else:
            LOG.info("Requested to skip pulling images ...\n")

        if not container.is_created():
            # Create the container first before running.
            # Create the container in appropriate Docker network
            container.network_id = self.docker_network_id
            container.create()

        container.start(input_data=input_data)

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
        :raises DockerImageNotFoundException: If the Docker image was not available in the server
        """
        stream = stream or sys.stderr
        try:
            result_itr = self.docker_client.api.pull(image_name, stream=True, decode=True)
        except docker.errors.ImageNotFound as ex:
            raise DockerImageNotFoundException(str(ex))

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


class DockerImageNotFoundException(Exception):
    pass
