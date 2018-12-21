"""
Representation of a generic Docker container
"""

import logging
import tarfile
import tempfile

import docker

from samcli.local.docker.attach_api import attach
from .utils import to_posix_path

LOG = logging.getLogger(__name__)


class Container(object):
    """
    Represents an instance of a Docker container with a specific configuration. The container is not actually created
    or executed until the appropriate methods are called. Each container instance is uniquely identified by an ID that
    the Docker Daemon creates when the container is started.

    NOTE: This class does not download container images. It should be pulled separately and made available before
          creating a container with this class
    """

    # This frame type value is coming directly from Docker Attach Stream API spec
    _STDOUT_FRAME_TYPE = 1
    _STDERR_FRAME_TYPE = 2

    def __init__(self,
                 image,
                 cmd,
                 working_dir,
                 host_dir,
                 memory_limit_mb=None,
                 exposed_ports=None,
                 entrypoint=None,
                 env_vars=None,
                 docker_client=None,
                 container_opts=None,
                 additional_volumes=None):
        """
        Initializes the class with given configuration. This does not automatically create or run the container.

        :param string image: Name of the Docker image to create container with
        :param string working_dir: Working directory for the container
        :param string host_dir: Directory in the host operating system that should be mounted to the ``working_dir`` on
            container
        :param list cmd: Command to pass to container
        :param int memory_limit_mb: Optional. Max limit of memory in MegaBytes this Lambda function can use.
        :param dict exposed_ports: Optional. Dict of ports to expose
        :param list entrypoint: Optional. Entry point process for the container. Defaults to the value in Dockerfile
        :param dict env_vars: Optional. Dict of environment variables to setup in the container
        """

        self._image = image
        self._cmd = cmd
        self._working_dir = working_dir
        self._host_dir = host_dir
        self._exposed_ports = exposed_ports
        self._entrypoint = entrypoint
        self._env_vars = env_vars
        self._memory_limit_mb = memory_limit_mb
        self._network_id = None
        self._container_opts = container_opts
        self._additional_volumes = additional_volumes

        # Use the given Docker client or create new one
        self.docker_client = docker_client or docker.from_env()

        # Runtime properties of the container. They won't have value until container is created or started
        self.id = None

    def create(self):
        """
        Calls Docker API to creates the Docker container instance. Creating the container does *not* run the container.
        Use ``start`` method to run the container

        :return string: ID of the created container
        :raise RuntimeError: If this method is called after a container already has been created
        """

        if self.is_created():
            raise RuntimeError("This container already exists. Cannot create again.")

        LOG.info("Mounting %s as %s:ro inside runtime container", self._host_dir, self._working_dir)

        kwargs = {
            "command": self._cmd,
            "working_dir": self._working_dir,
            "volumes": {
                self._host_dir: {
                    # Mount the host directory as "read only" directory inside container at working_dir
                    # https://docs.docker.com/storage/bind-mounts
                    # Mount the host directory as "read only" inside container
                    "bind": self._working_dir,
                    "mode": "ro"
                }
            },
            # We are not running an interactive shell here.
            "tty": False
        }

        if self._container_opts:
            kwargs.update(self._container_opts)

        if self._additional_volumes:
            kwargs["volumes"].update(self._additional_volumes)

        # Make sure all mounts are of posix path style.
        kwargs["volumes"] = {to_posix_path(host_dir): mount for host_dir, mount in kwargs["volumes"].items()}

        if self._env_vars:
            kwargs["environment"] = self._env_vars

        if self._exposed_ports:
            kwargs["ports"] = self._exposed_ports

        if self._entrypoint:
            kwargs["entrypoint"] = self._entrypoint

        if self._memory_limit_mb:
            # Ex: 128m => 128MB
            kwargs["mem_limit"] = "{}m".format(self._memory_limit_mb)

        if self.network_id == 'host':
            kwargs["network_mode"] = self.network_id

        real_container = self.docker_client.containers.create(self._image, **kwargs)
        self.id = real_container.id

        if self.network_id and self.network_id != 'host':
            network = self.docker_client.networks.get(self.network_id)
            network.connect(self.id)

        return self.id

    def delete(self):
        """
        Removes a container that was created earlier.
        """
        if not self.is_created():
            LOG.debug("Container was not created. Skipping deletion")
            return

        try:
            self.docker_client.containers\
                .get(self.id)\
                .remove(force=True)  # Remove a container, even if it is running
        except docker.errors.NotFound:
            # Container is already not there
            LOG.debug("Container with ID %s does not exist. Skipping deletion", self.id)
        except docker.errors.APIError as ex:
            msg = str(ex)
            removal_in_progress = ("removal of container" in msg) and ("is already in progress" in msg)

            # When removal is already started, Docker API will throw an exception
            # Skip such exceptions.
            if not removal_in_progress:
                raise ex

        self.id = None

    def start(self, input_data=None):
        """
        Calls Docker API to start the container. The container must be created at the first place to run.
        It waits for the container to complete, fetches both stdout and stderr logs and returns through the
        given streams.

        Parameters
        ----------
        input_data
            Optional. Input data sent to the container through container's stdin.
        """

        if input_data:
            raise ValueError("Passing input through container's stdin is not supported")

        if not self.is_created():
            raise RuntimeError("Container does not exist. Cannot start this container")

        # Get the underlying container instance from Docker API
        real_container = self.docker_client.containers.get(self.id)

        # Start the container
        real_container.start()

    def wait_for_logs(self, stdout=None, stderr=None):

        # Return instantly if we don't have to fetch any logs
        if not stdout and not stderr:
            return

        if not self.is_created():
            raise RuntimeError("Container does not exist. Cannot get logs for this container")

        real_container = self.docker_client.containers.get(self.id)

        # Fetch both stdout and stderr streams from Docker as a single iterator.
        logs_itr = attach(self.docker_client,
                          container=real_container,
                          stdout=True,
                          stderr=True,
                          logs=True)

        self._write_container_output(logs_itr, stdout=stdout, stderr=stderr)

    def copy(self, from_container_path, to_host_path):

        if not self.is_created():
            raise RuntimeError("Container does not exist. Cannot get logs for this container")

        real_container = self.docker_client.containers.get(self.id)

        LOG.debug("Copying from container: %s -> %s", from_container_path, to_host_path)
        with tempfile.NamedTemporaryFile() as fp:
            tar_stream, _ = real_container.get_archive(from_container_path)
            for data in tar_stream:
                fp.write(data)

            # Seek the handle back to start of file for tarfile to use
            fp.seek(0)

            with tarfile.open(fileobj=fp, mode='r') as tar:
                tar.extractall(path=to_host_path)

    @staticmethod
    def _write_container_output(output_itr, stdout=None, stderr=None):
        """
        Based on the data returned from the Container output, via the iterator, write it to the appropriate streams

        Parameters
        ----------
        output_itr: Iterator
            Iterator returned by the Docker Attach command
        stdout: samcli.lib.utils.stream_writer.StreamWriter, optional
            Stream writer to write stdout data from Container into
        stderr: samcli.lib.utils.stream_writer.StreamWriter, optional
            Stream writer to write stderr data from the Container into
        """

        # Iterator returns a tuple of (frame_type, data) where the frame type determines which stream we write output
        # to
        for frame_type, data in output_itr:

            if frame_type == Container._STDOUT_FRAME_TYPE and stdout:
                # Frame type 1 is stdout data.
                stdout.write(data)

            elif frame_type == Container._STDERR_FRAME_TYPE and stderr:
                # Frame type 2 is stderr data.
                stderr.write(data)

            else:
                # Either an unsupported frame type or stream for this frame type is not configured
                LOG.debug("Dropping Docker container output because of unconfigured frame type. "
                          "Frame Type: %s. Data: %s", frame_type, data)

    @property
    def network_id(self):
        """
        Gets the ID of the network this container connects to
        :return string: ID of the network
        """
        return self._network_id

    @network_id.setter
    def network_id(self, value):
        """
        Set the ID of network that this container should connect to

        :param string value: Value of the network ID
        """
        self._network_id = value

    @property
    def image(self):
        """
        Returns the image used by this container

        :return string: Name of the container image
        """
        return self._image

    def is_created(self):
        """
        Checks if a container exists?

        :return bool: True if the container was created
        """
        return self.id is not None
