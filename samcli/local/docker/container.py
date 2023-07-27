"""
Representation of a generic Docker container
"""
import logging
import os
import pathlib
import shutil
import socket
import tempfile
import threading
import time
from typing import Optional

import docker
import requests
from docker.errors import NotFound as DockerNetworkNotFound

from samcli.lib.constants import DOCKER_MIN_API_VERSION
from samcli.lib.utils.retry import retry
from samcli.lib.utils.tar import extract_tarfile
from samcli.local.docker.effective_user import ROOT_USER_ID, EffectiveUser
from samcli.local.docker.exceptions import ContainerNotStartableException, PortAlreadyInUse
from samcli.local.docker.utils import NoFreePortsError, find_free_port, to_posix_path

LOG = logging.getLogger(__name__)

CONTAINER_CONNECTION_TIMEOUT = float(os.environ.get("SAM_CLI_CONTAINER_CONNECTION_TIMEOUT", 20))


class ContainerResponseException(Exception):
    """
    Exception raised when unable to communicate with RAPID APIs on a running container.
    """


class ContainerConnectionTimeoutException(Exception):
    """
    Exception raised when timeout was reached while attempting to establish a connection to a container.
    """


class Container:
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
    RAPID_PORT_CONTAINER = "8080"
    URL = "http://{host}:{port}/2015-03-31/functions/{function_name}/invocations"
    # Set connection timeout to 1 sec to support the large input.
    RAPID_CONNECTION_TIMEOUT = 1

    def __init__(
        self,
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
        additional_volumes=None,
        container_host="localhost",
        container_host_interface="127.0.0.1",
        mount_with_write: bool = False,
        host_tmp_dir: Optional[str] = None,
    ):
        """
        Initializes the class with given configuration. This does not automatically create or run the container.

        :param str image: Name of the Docker image to create container with
        :param str cmd: Command to pass to container
        :param str working_dir: Working directory for the container
        :param str host_dir: Directory in the host operating system that should be mounted to the ``working_dir`` on
            container
        :param int memory_limit_mb: Optional. Max limit of memory in MegaBytes this Lambda function can use.
        :param dict exposed_ports: Optional. Dict of ports to expose
        :param dict entrypoint: Optional. Entry point process for the container. Defaults to the value in Dockerfile
        :param dict env_vars: Optional. Dict of environment variables to setup in the container
        :param docker_client: Optional, a docker client to replace the default one loaded from env
        :param container_opts: Optional, a dictionary containing the container options
        :param additional_volumes: Optional list of additional volumes
        :param string container_host: Optional. Host of locally emulated Lambda container
        :param string container_host_interface: Optional. Interface that Docker host binds ports to
        :param bool mount_with_write: Optional. Mount source code directory with write permissions when
            building on container
        :param string host_tmp_dir: Optional. Temporary directory on the host when mounting with write permissions.
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
        self._logs_thread = None

        # Use the given Docker client or create new one
        self.docker_client = docker_client or docker.from_env(version=DOCKER_MIN_API_VERSION)

        # Runtime properties of the container. They won't have value until container is created or started
        self.id = None

        # aws-lambda-rie defaults to 8080 as the port, however that's a common port. A port is chosen by
        # selecting the first free port in a range that's not ephemeral.
        self._start_port_range = 5000
        self._end_port_range = 9000

        self._container_host = container_host
        self._container_host_interface = container_host_interface
        self._mount_with_write = mount_with_write
        self._host_tmp_dir = host_tmp_dir

        try:
            self.rapid_port_host = find_free_port(start=self._start_port_range, end=self._end_port_range)
        except NoFreePortsError as ex:
            raise ContainerNotStartableException(str(ex)) from ex

    def create(self):
        """
        Calls Docker API to creates the Docker container instance. Creating the container does *not* run the container.
        Use ``start`` method to run the container

        :return string: ID of the created container
        :raise RuntimeError: If this method is called after a container already has been created
        """

        if self.is_created():
            raise RuntimeError("This container already exists. Cannot create again.")

        _volumes = {}

        if self._host_dir:
            mount_mode = "rw,delegated" if self._mount_with_write else "ro,delegated"
            LOG.info("Mounting %s as %s:%s, inside runtime container", self._host_dir, self._working_dir, mount_mode)

            _volumes = {
                self._host_dir: {
                    # Mount the host directory inside container at working_dir
                    # https://docs.docker.com/storage/bind-mounts
                    "bind": self._working_dir,
                    "mode": mount_mode,
                }
            }

        kwargs = {
            "command": self._cmd,
            "working_dir": self._working_dir,
            "volumes": _volumes,
            # We are not running an interactive shell here.
            "tty": False,
            # Set proxy configuration from global Docker config file
            "use_config_proxy": True,
        }

        # Get effective user when building lambda and mounting with write permissions
        # Pass effective user to docker run CLI as "--user" option in the format of uid[:gid]
        # to run docker as current user instead of root
        # Skip if current user is root on posix systems or non-posix systems
        effective_user = EffectiveUser.get_current_effective_user().to_effective_user_str()
        if self._mount_with_write and effective_user and effective_user != ROOT_USER_ID:
            LOG.debug("Detect non-root user, will pass argument '--user %s' to container", effective_user)
            kwargs["user"] = effective_user

        if self._container_opts:
            kwargs.update(self._container_opts)

        if self._additional_volumes:
            kwargs["volumes"].update(self._additional_volumes)

        # Make sure all mounts are of posix path style.
        kwargs["volumes"] = {to_posix_path(host_dir): mount for host_dir, mount in kwargs["volumes"].items()}

        if self._env_vars:
            kwargs["environment"] = self._env_vars

        kwargs["ports"] = {self.RAPID_PORT_CONTAINER: (self._container_host_interface, self.rapid_port_host)}

        if self._exposed_ports:
            kwargs["ports"].update(
                {
                    container_port: (self._container_host_interface, host_port)
                    for container_port, host_port in self._exposed_ports.items()
                }
            )

        if self._entrypoint:
            kwargs["entrypoint"] = self._entrypoint

        if self._memory_limit_mb:
            # Ex: 128m => 128MB
            kwargs["mem_limit"] = "{}m".format(self._memory_limit_mb)

        real_container = self.docker_client.containers.create(self._image, **kwargs)
        self.id = real_container.id

        self._logs_thread = None

        if self.network_id and self.network_id != "host":
            try:
                network = self.docker_client.networks.get(self.network_id)
                network.connect(self.id)
            except DockerNetworkNotFound:
                # stop and delete the created container before raising the exception
                real_container.remove(force=True)
                raise

        return self.id

    def stop(self, timeout=3):
        """
        Stop a container, with a given number of seconds between sending SIGTERM and SIGKILL.

        Parameters
        ----------
        timeout
            Optional. Number of seconds between SIGTERM and SIGKILL. Effectively, the amount of time
            the container has to perform shutdown steps. Default: 3
        """
        if not self.is_created():
            LOG.debug("Container was not created, cannot run stop.")
            return

        try:
            self.docker_client.containers.get(self.id).stop(timeout=timeout)
        except docker.errors.NotFound:
            # Container is already removed
            LOG.debug("Container with ID %s does not exist. Cannot stop!", self.id)
        except docker.errors.APIError as ex:
            msg = str(ex)
            removal_in_progress = ("removal of container" in msg) and ("is already in progress" in msg)

            # When removal is already started, Docker API will throw an exception
            # Skip such exceptions and log
            if not removal_in_progress:
                raise ex
            LOG.debug("Container removal is in progress, skipping exception: %s", msg)

    def delete(self):
        """
        Removes a container that was created earlier.
        """
        if not self.is_created():
            LOG.debug("Container was not created. Skipping deletion")
            return

        try:
            self.docker_client.containers.get(self.id).remove(force=True)  # Remove a container, even if it is running
        except docker.errors.NotFound:
            # Container is already not there
            LOG.debug("Container with ID %s does not exist. Skipping deletion", self.id)
        except docker.errors.APIError as ex:
            msg = str(ex)
            removal_in_progress = ("removal of container" in msg) and ("is already in progress" in msg)

            # When removal is already started, Docker API will throw an exception
            # Skip such exceptions and log
            if not removal_in_progress:
                raise ex
            LOG.debug("Container removal is in progress, skipping exception: %s", msg)
        finally:
            # Remove tmp dir on the host
            if self._host_tmp_dir:
                host_tmp_dir_path = pathlib.Path(self._host_tmp_dir)
                if host_tmp_dir_path.exists():
                    shutil.rmtree(self._host_tmp_dir)
                    LOG.debug("Successfully removed temporary directory %s on the host.", self._host_tmp_dir)

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

        # Make tmp dir on the host
        if self._mount_with_write and self._host_tmp_dir and not os.path.exists(self._host_tmp_dir):
            os.makedirs(self._host_tmp_dir)
            LOG.debug("Successfully created temporary directory %s on the host.", self._host_tmp_dir)

        # Get the underlying container instance from Docker API
        real_container = self.docker_client.containers.get(self.id)

        try:
            # Start the container
            real_container.start()
        except docker.errors.APIError as ex:
            if "Ports are not available" in str(ex):
                raise PortAlreadyInUse(ex.explanation.decode()) from ex
            raise ex

    @retry(exc=requests.exceptions.RequestException, exc_raise=ContainerResponseException)
    def wait_for_http_response(self, name, event, stdout):
        # TODO(sriram-mv): `aws-lambda-rie` is in a mode where the function_name is always "function"
        # NOTE(sriram-mv): There is a connection timeout set on the http call to `aws-lambda-rie`, however there is not
        # a read time out for the response received from the server.

        resp = requests.post(
            self.URL.format(host=self._container_host, port=self.rapid_port_host, function_name="function"),
            data=event.encode("utf-8"),
            timeout=(self.RAPID_CONNECTION_TIMEOUT, None),
        )
        stdout.write(resp.content)

    def wait_for_result(self, full_path, event, stdout, stderr, start_timer=None):
        # NOTE(sriram-mv): Let logging happen in its own thread, so that a http request can be sent.
        # NOTE(sriram-mv): All logging is re-directed to stderr, so that only the lambda function return
        # will be written to stdout.

        # the log thread will not be closed until the container itself got deleted,
        # so as long as the container is still there, no need to start a new log thread
        if not self._logs_thread or not self._logs_thread.is_alive():
            self._logs_thread = threading.Thread(target=self.wait_for_logs, args=(stderr, stderr), daemon=True)
            self._logs_thread.start()

        # wait_for_http_response will attempt to establish a connection to the socket
        # but it'll fail if the socket is not listening yet, so we wait for the socket
        self._wait_for_socket_connection()

        # start the timer for function timeout right before executing the function, as waiting for the socket
        # can take some time
        timer = start_timer() if start_timer else None
        self.wait_for_http_response(full_path, event, stdout)
        if timer:
            timer.cancel()

    def wait_for_logs(self, stdout=None, stderr=None):
        # Return instantly if we don't have to fetch any logs
        if not stdout and not stderr:
            return

        if not self.is_created():
            raise RuntimeError("Container does not exist. Cannot get logs for this container")

        real_container = self.docker_client.containers.get(self.id)

        # Fetch both stdout and stderr streams from Docker as a single iterator.
        logs_itr = real_container.attach(stream=True, logs=True, demux=True)

        self._write_container_output(logs_itr, stdout=stdout, stderr=stderr)

    def _wait_for_socket_connection(self) -> None:
        """
        Waits for a successful connection to the socket used to communicate with Docker.
        """

        start_time = time.time()
        while not self._can_connect_to_socket():
            time.sleep(0.1)
            current_time = time.time()
            if current_time - start_time > CONTAINER_CONNECTION_TIMEOUT:
                raise ContainerConnectionTimeoutException(
                    f"Timed out while attempting to establish a connection to the container. You can increase this "
                    f"timeout by setting the SAM_CLI_CONTAINER_CONNECTION_TIMEOUT environment variable. "
                    f"The current timeout is {CONTAINER_CONNECTION_TIMEOUT} (seconds)."
                )

    def _can_connect_to_socket(self) -> bool:
        """
        Checks if able to connect successully to the socket used to communicate with Docker.
        """

        a_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        location = (self._container_host, self.rapid_port_host)
        # connect_ex returns 0 if connection succeeded
        connection_succeeded = not a_socket.connect_ex(location)
        a_socket.close()
        return connection_succeeded

    def copy(self, from_container_path, to_host_path) -> None:
        """Copies a path from container into host path"""

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

            extract_tarfile(file_obj=fp, unpack_dir=to_host_path)

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

        # following iterator might throw an exception (see: https://github.com/aws/aws-sam-cli/issues/4222)
        try:
            # Iterator returns a tuple of (stdout, stderr)
            for stdout_data, stderr_data in output_itr:
                if stdout_data and stdout:
                    stdout.write(stdout_data)

                if stderr_data and stderr:
                    stderr.write(stderr_data)
        except Exception as ex:
            LOG.debug("Failed to get the logs from the container", exc_info=ex)

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
        Checks if the real container exists?

        Returns
        -------
        bool
            True if the container is created
        """
        if self.id:
            try:
                self.docker_client.containers.get(self.id)
                return True
            except docker.errors.NotFound:
                return False
        return False

    def is_running(self):
        """
        Checks if the real container status is running

        Returns
        -------
        bool
            True if the container is running
        """
        try:
            real_container = self.docker_client.containers.get(self.id)
            return real_container.status == "running"
        except docker.errors.NotFound:
            return False
