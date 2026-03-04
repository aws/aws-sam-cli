"""
Container for AWS Lambda Durable Functions Emulator.
"""

import logging
import os
import time
from http import HTTPStatus
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Optional

import docker
import requests
from click import ClickException

from samcli.lib.build.utils import _get_host_architecture
from samcli.lib.clients.lambda_client import DurableFunctionsClient
from samcli.lib.utils.tar import create_tarball
from samcli.local.docker.utils import get_tar_filter_for_windows, get_validated_container_client, is_image_current

LOG = logging.getLogger(__name__)


class DurableFunctionsEmulatorContainer:
    """
    Manages the durable functions emulator container.
    """

    _RAPID_SOURCE_PATH = Path(__file__).parent.joinpath("..", "rapid").resolve()
    _EMULATOR_IMAGE = "public.ecr.aws/ubuntu/ubuntu:24.04"
    _EMULATOR_IMAGE_PREFIX = "samcli/durable-execution-emulator"
    _CONTAINER_NAME = "sam-durable-execution-emulator"
    _EMULATOR_DATA_DIR_NAME = ".durable-executions-local"
    _EMULATOR_DEFAULT_STORE_TYPE = "sqlite"
    EMULATOR_PORT = 9014

    """
    Allow overriding the emulator to a local instance of the emulator server.
    This is useful for testing changes in the underlying testing library that
    implements the state management logic.
    """
    ENV_EXTERNAL_EMULATOR_PORT = "DURABLE_EXECUTIONS_EXTERNAL_EMULATOR_PORT"

    """
    Allow overriding the emulator to use a different storetype. The valid options
    are either sqlite (default), or filesystem. The filesystem has a more verbose
    persistence style which can be useful for debugging.
    """
    ENV_STORE_TYPE = "DURABLE_EXECUTIONS_STORE_TYPE"

    """
    Allow overriding the timescale used by the emulator. For example, if you have
    a context.wait(3 months), you probably don't want to actually wait 3 months in
    a local development loop. This lets you override that!
    """
    ENV_TIME_SCALE = "DURABLE_EXECUTIONS_TIME_SCALE"

    """
    Capture the logs from the emulator on cleanup - this can be useful for debugging
    what happened, since once the container is gone, the logs are too.
    """
    ENV_CAPTURE_LOGS = "DURABLE_EXECUTIONS_CAPTURE_LOGS"

    """
    Allow overriding the container name. This enables running multiple emulator containers
    simultaneously without conflicts.
    """
    ENV_CONTAINER_NAME = "DURABLE_EXECUTIONS_CONTAINER_NAME"

    """
    Allow overriding the emulator port. This enables running multiple emulator containers
    on different ports simultaneously.
    """
    ENV_EMULATOR_PORT = "DURABLE_EXECUTIONS_EMULATOR_PORT"

    def __init__(self, container_client=None, existing_container=None):
        self._docker_client_param = container_client
        self._validated_docker_client: Optional[docker.DockerClient] = None
        self.container = existing_container
        self.lambda_client: Optional[DurableFunctionsClient] = None

        self.port = self._get_emulator_port()

        if self._is_external_emulator():
            self._container_name = None  # Not needed in external mode
            LOG.info(f"Using external durable functions emulator: localhost:{self.port}")
        else:
            self._container_name = self._get_emulator_container_name()
            LOG.debug(f"Emulator port: {self.port}")

    def _is_external_emulator(self):
        """Check if we're using an external emulator via environment variable."""
        return bool(os.environ.get(self.ENV_EXTERNAL_EMULATOR_PORT))

    def _get_emulator_container_name(self):
        """Get container name from environment variable or use default."""
        return os.environ.get(self.ENV_CONTAINER_NAME, self._CONTAINER_NAME)

    def _get_port(self, external_port_env_var, override_port_env_var, default_port):
        """
        Get port from environment variables. External emulator port takes first priority,
        followed by any override set.

        Args:
            external_port_env_var: External emulator port environment variable
            override_port_env_var: Override port environment variable
            default_port: Default port if neither environment variable is set

        Returns:
            int: The port number

        Raises:
            RuntimeError: If port value is not a valid integer
        """
        port_str = os.environ.get(external_port_env_var) or os.environ.get(override_port_env_var)
        if port_str:
            try:
                return int(port_str)
            except ValueError:
                env_var = external_port_env_var if os.environ.get(external_port_env_var) else override_port_env_var
                raise RuntimeError(f"Invalid port number in {env_var}: {port_str}")
        return default_port

    def _get_emulator_port(self):
        """
        Get the emulator port from environment variable or use default.

        External emulator mode allows developers to run against their own local testing server
        directly, skipping container creation for a faster development loop instead of needing
        to build a new emulator image.
        """
        return self._get_port(self.ENV_EXTERNAL_EMULATOR_PORT, self.ENV_EMULATOR_PORT, self.EMULATOR_PORT)

    def _get_emulator_store_type(self):
        """Get the store type from environment variable or use default."""
        store_type = os.environ.get(self.ENV_STORE_TYPE, self._EMULATOR_DEFAULT_STORE_TYPE)
        LOG.debug(f"Creating durable functions emulator container with store type: {store_type}")
        return store_type

    def _get_emulator_time_scale(self):
        """Get the execution time scale from environment variable or use default timescale of 1."""
        return os.environ.get(self.ENV_TIME_SCALE, "1")

    def _get_emulator_data_dir(self):
        """Get the path to the emulator data directory."""
        return os.path.join(os.getcwd(), self._EMULATOR_DATA_DIR_NAME)

    def _capture_emulator_logs(self):
        """Capture and save emulator container logs to file."""
        if not os.environ.get(self.ENV_CAPTURE_LOGS) or not self.container:
            return

        try:
            logs = self.container.logs().decode("utf-8")
            emulator_data_dir = self._get_emulator_data_dir()
            timestamp = time.strftime("%Y-%m-%dT%H-%M-%S")
            log_file = os.path.join(emulator_data_dir, f"durable-execution-emulator-{timestamp}.log")
            with open(log_file, "w") as f:
                f.write(logs)
            LOG.info(f"Emulator logs saved to {log_file}")
        except Exception as e:
            LOG.warning(f"Failed to capture emulator logs: {e}")

    def _get_emulator_environment(self):
        """
        Get the environment variables for the emulator container.
        """
        return {
            "HOST": "0.0.0.0",
            "PORT": str(self.port),
            "LOG_LEVEL": "DEBUG",
            # The emulator needs to have credential variables set, or else it will fail to create boto clients.
            "AWS_ACCESS_KEY_ID": "foo",
            "AWS_SECRET_ACCESS_KEY": "bar",
            "AWS_DEFAULT_REGION": "us-east-1",
            "EXECUTION_STORE_TYPE": self._get_emulator_store_type(),
            "EXECUTION_TIME_SCALE": self._get_emulator_time_scale(),
        }

    @property
    def _docker_client(self) -> docker.DockerClient:
        """
        Lazy initialization of Docker client. Only validates container runtime when actually accessed.
        This prevents unnecessary container runtime validation for builds that don't require containers.
        """
        if self._validated_docker_client is None:
            self._validated_docker_client = self._docker_client_param or get_validated_container_client()
        return self._validated_docker_client

    def _get_emulator_binary_name(self):
        """Get the emulator binary name based on current architecture."""
        arch = _get_host_architecture()
        return f"aws-durable-execution-emulator-{arch}"

    def _generate_emulator_dockerfile(self, emulator_binary_name: str) -> str:
        """Generate Dockerfile content for emulator image."""
        return (
            f"FROM {self._EMULATOR_IMAGE}\n"
            f"COPY {emulator_binary_name} /usr/local/bin/{emulator_binary_name}\n"
            f"RUN chmod +x /usr/local/bin/{emulator_binary_name}\n"
        )

    def _get_emulator_image_tag(self, emulator_binary_name: str) -> str:
        """Get the Docker image tag for the emulator."""
        return f"{self._EMULATOR_IMAGE_PREFIX}:{emulator_binary_name}"

    def _build_emulator_image(self):
        """Build Docker image with emulator binary."""
        emulator_binary_name = self._get_emulator_binary_name()
        binary_path = self._RAPID_SOURCE_PATH / emulator_binary_name

        if not binary_path.exists():
            raise RuntimeError(f"Durable Functions Emulator binary not found at {binary_path}")

        image_tag = self._get_emulator_image_tag(emulator_binary_name)

        # Check if image already exists
        try:
            self._docker_client.images.get(image_tag)
            LOG.debug(f"Emulator image {image_tag} already exists")
            return image_tag
        except docker.errors.ImageNotFound:
            LOG.debug(f"Building emulator image {image_tag}")

        # Generate Dockerfile content
        dockerfile_content = self._generate_emulator_dockerfile(emulator_binary_name)

        # Write Dockerfile to temp location and build image
        with NamedTemporaryFile(mode="w", suffix="_Dockerfile") as dockerfile:
            dockerfile.write(dockerfile_content)
            dockerfile.flush()

            # Prepare tar paths for build context
            tar_paths = {
                dockerfile.name: "Dockerfile",
                str(binary_path): emulator_binary_name,
            }

            # Use shared tar filter for Windows compatibility
            tar_filter = get_tar_filter_for_windows()

            # Build image using create_tarball utility
            with create_tarball(tar_paths, tar_filter=tar_filter, dereference=True) as tarballfile:
                try:
                    self._docker_client.images.build(fileobj=tarballfile, custom_context=True, tag=image_tag, rm=True)
                    LOG.info(f"Built emulator image {image_tag}")
                    return image_tag
                except Exception as e:
                    raise ClickException(f"Failed to build emulator image: {e}")

    def _pull_image_if_needed(self):
        """Pull the emulator image if it doesn't exist locally or is out of date."""
        try:
            self._docker_client.images.get(self._EMULATOR_IMAGE)
            LOG.debug(f"Emulator image {self._EMULATOR_IMAGE} exists locally")

            if is_image_current(self._docker_client, self._EMULATOR_IMAGE):
                LOG.debug("Local emulator image is up-to-date")
                return

            LOG.debug("Local image is out of date and will be updated to the latest version")
        except docker.errors.ImageNotFound:
            LOG.debug(f"Pulling emulator image {self._EMULATOR_IMAGE}...")

        try:
            self._docker_client.images.pull(self._EMULATOR_IMAGE)
            LOG.info(f"Successfully pulled image {self._EMULATOR_IMAGE}")
        except Exception as e:
            raise ClickException(f"Failed to pull emulator image {self._EMULATOR_IMAGE}: {e}")

    def start(self):
        """Start the emulator container."""
        # Skip starting container if using external emulator
        if self._is_external_emulator():
            LOG.info("Using external durable functions emulator, skipping container start")
            return

        emulator_binary_name = self._get_emulator_binary_name()

        """
        Create persistent volume for execution data to be stored in.
        This will be at the current working directory. If a user is running `sam local invoke` in the same
        directory as their SAM template, then they will see this `.durable-executions-local/` directory there.
        """
        emulator_data_dir = self._get_emulator_data_dir()
        os.makedirs(emulator_data_dir, exist_ok=True)

        volumes = {
            emulator_data_dir: {"bind": "/tmp/.durable-executions-local", "mode": "rw"},
        }

        # Build image with emulator binary
        image_tag = self._build_emulator_image()

        LOG.debug(f"Creating container with name={self._container_name}, port={self.port}")
        self.container = self._docker_client.containers.create(
            image=image_tag,
            command=[f"/usr/local/bin/{emulator_binary_name}", "--host", "0.0.0.0", "--port", str(self.port)],
            name=self._container_name,
            ports={f"{self.port}/tcp": self.port},
            volumes=volumes,
            environment=self._get_emulator_environment(),
            working_dir="/tmp/.durable-executions-local",
            extra_hosts={"host.docker.internal": "host-gateway"},
        )

        # Start the container
        self.container.start()

        # Wait for container to be ready
        self._wait_for_ready()

        # Create lambda client after container is ready
        self.lambda_client = DurableFunctionsClient.create(host="localhost", port=self.port)

        LOG.debug(f"Durable Functions Emulator container started: {self.container.short_id}")

    def start_or_attach(self) -> bool:
        """Create and start a new container or attach to an existing one if available.
        For external emulators, just creates the lambda client.

        Returns:
            bool: True if a running container was attached to, False if a new container was started
        """
        # Handle external emulator
        if self._is_external_emulator():
            self.lambda_client = DurableFunctionsClient.create(host="localhost", port=self.port)
            return True

        try:
            # Try to find existing container
            LOG.debug(f"Looking for existing container: {self._container_name}")
            existing_container = self._docker_client.containers.get(self._container_name)
            LOG.debug(f"Found existing container {self._container_name} with status: {existing_container.status}")

            if existing_container.status == "running":
                LOG.debug("Reusing existing running emulator container")
                self.container = existing_container
                self.lambda_client = DurableFunctionsClient.create(host="localhost", port=self.port)
                return True
            else:
                try:
                    existing_container.stop()
                    existing_container.remove()
                except Exception as e:
                    LOG.warning(f"Could not remove existing container: {e}")
        except Exception:
            # Container doesn't exist, proceed to create new one
            LOG.debug("No existing container found, creating new one")

        # Create new container
        self.start()
        return False

    def stop(self):
        """Stop and remove the emulator container."""
        if self._is_external_emulator():
            return

        if self.container:
            try:
                self._capture_emulator_logs()
                self.container.stop()
                self.container.remove()
                LOG.debug("Durable Functions Emulator container stopped and removed")
            except docker.errors.NotFound:
                # Container already removed, ignore
                LOG.debug("Container already removed, skipping cleanup")
            except Exception as e:
                LOG.error(f"Error stopping Durable Functions Emulator container: {e}")
            finally:
                self.container = None

    def is_running(self):
        """Check if the emulator container is running."""
        if not self.container:
            return False
        try:
            self.container.reload()
            return self.container.status == "running"
        except Exception:
            return False

    def get_logs(self, tail=50):
        """Get logs from the emulator container."""
        if self.container:
            try:
                return self.container.logs(tail=tail).decode("utf-8")
            except Exception as e:
                return f"Could not retrieve logs: {e}"
        return "Durable Functions Emulator container not started"

    def start_durable_execution(self, execution_name, event, lambda_endpoint, durable_config):
        """Start a durable execution via the emulator API."""
        base_url = f"http://localhost:{self.port}"
        url = f"{base_url}/start-durable-execution"

        payload = {
            "AccountId": "123456789012",
            "FunctionName": "function",
            "FunctionQualifier": "$LATEST",
            "ExecutionName": execution_name,
            "ExecutionTimeoutSeconds": durable_config.get("ExecutionTimeout"),
            "ExecutionRetentionPeriodDays": durable_config.get("RetentionPeriodInDays"),
            "Input": event,
            "LambdaEndpoint": lambda_endpoint,
        }

        try:
            response = requests.post(url, json=payload, timeout=30)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            error_msg = f"Failed to start durable execution: {e}"
            if hasattr(e, "response") and e.response is not None:
                error_msg += f" - Status: {e.response.status_code}, Response: {e.response.text}"
            LOG.error(error_msg)
            raise RuntimeError(error_msg)

    def _wait_for_ready(self, timeout=30):
        """Wait for emulator to be ready."""
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                self.container.reload()
                if self.container.status != "running":
                    raise RuntimeError(
                        f"Durable Functions Emulator container exited with status: {self.container.status}"
                    )

                response = requests.get(f"http://localhost:{self.port}/health", timeout=1)
                if response.status_code == HTTPStatus.OK:
                    return
            except requests.exceptions.RequestException:
                pass
            except Exception as e:
                LOG.error(f"Durable Functions Emulator container encounters error during health check: {e}")
                break

            time.sleep(0.5)

        # Get logs for debugging
        try:
            logs = self.container.logs().decode("utf-8")
            LOG.error(f"Container logs: {logs}")
        except Exception:
            pass

        raise RuntimeError(f"Durable Functions Emulator container failed to become ready within {timeout} seconds")
