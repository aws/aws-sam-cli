"""
Container for AWS Lambda Durable Functions Emulator.
"""

import logging
import os
import time
from http import HTTPStatus
from pathlib import Path
from typing import Optional

import docker
import requests
from click import ClickException

from samcli.lib.build.utils import _get_host_architecture
from samcli.lib.clients.lambda_client import DurableFunctionsClient
from samcli.local.docker.utils import (
    get_validated_container_client,
    is_image_current,
    to_posix_path,
)

LOG = logging.getLogger(__name__)


class DurableFunctionsEmulatorContainer:
    """
    Manages the durable functions emulator container.
    """

    _RAPID_SOURCE_PATH = Path(__file__).parent.joinpath("..", "rapid").resolve()
    _EMULATOR_IMAGE_PREFIX = "public.ecr.aws/durable-functions/aws-durable-execution-emulator"
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

    """
    Allow pinning to a specific emulator image tag/version
    """
    ENV_EMULATOR_IMAGE_TAG = "DURABLE_EXECUTIONS_EMULATOR_IMAGE_TAG"

    def __init__(self, container_client=None, existing_container=None, skip_pull_image=False):
        self._docker_client_param = container_client
        self._validated_docker_client: Optional[docker.DockerClient] = None
        self.container = existing_container
        self.lambda_client: Optional[DurableFunctionsClient] = None
        self._skip_pull_image = skip_pull_image

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

    def _get_emulator_image_tag(self):
        """Get the emulator image tag from environment variable or use default."""
        return os.environ.get(self.ENV_EMULATOR_IMAGE_TAG, "latest")

    def _get_emulator_image(self):
        """Get the full emulator image name with tag."""
        return f"{self._EMULATOR_IMAGE_PREFIX}:{self._get_emulator_image_tag()}"

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
            "DURABLE_EXECUTION_TIME_SCALE": self._get_emulator_time_scale(),
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

    def _pull_image_if_needed(self):
        local_image_exists = False
        """Pull the emulator image if it doesn't exist locally or is out of date."""
        try:
            self._docker_client.images.get(self._get_emulator_image())
            local_image_exists = True
            LOG.debug(f"Emulator image {self._get_emulator_image()} exists locally")
            if is_image_current(self._docker_client, self._get_emulator_image()):
                LOG.debug("Local emulator image is up-to-date")
                return

            LOG.debug("Local image is out of date and will be updated to the latest version")
        except docker.errors.ImageNotFound:
            LOG.debug(f"Pulling emulator image {self._get_emulator_image()}...")

        try:
            if self._skip_pull_image and local_image_exists:
                LOG.debug("Skipping pulling new emulator image")
                return
            self._docker_client.images.pull(self._get_emulator_image())
            LOG.info(f"Successfully pulled image {self._get_emulator_image()}")
        except Exception as e:
            if local_image_exists:
                LOG.debug(
                    f"Using existing local emulator image since we failed to pull emulator image "
                    f"{self._get_emulator_image()}: {e}"
                )
            else:
                raise ClickException(f"Failed to pull emulator image {self._get_emulator_image()}: {e}")

    def start(self):
        """Start the emulator container."""
        # Skip starting container if using external emulator
        if self._is_external_emulator():
            LOG.info("Using external durable functions emulator, skipping container start")
            return

        """
        Create persistent volume for execution data to be stored in.
        This will be at the current working directory. If a user is running `sam local invoke` in the same
        directory as their SAM template, then they will see this `.durable-executions-local/` directory there.
        """
        emulator_data_dir = self._get_emulator_data_dir()
        os.makedirs(emulator_data_dir, exist_ok=True)

        volumes = {
            to_posix_path(emulator_data_dir): {"bind": "/tmp/.durable-executions-local", "mode": "rw"},
        }

        self._pull_image_if_needed()

        LOG.debug(f"Creating container with name={self._container_name}, port={self.port}")
        self.container = self._docker_client.containers.create(
            image=self._get_emulator_image(),
            command=[
                "dex-local-runner",
                "start-server",
                "--host",
                "0.0.0.0",
                "--port",
                str(self.port),
                "--log-level",
                "DEBUG",
                "--lambda-endpoint",
                "http://host.docker.internal:3001",
                "--store-type",
                self._get_emulator_store_type(),
                "--store-path",
                "/tmp/.durable-executions-local/durable-executions.db",  # this is the path within the container
            ],
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

        raise RuntimeError(
            f"Durable Functions Emulator container failed to become ready within {timeout} seconds. "
            "You may set the DURABLE_EXECUTIONS_EMULATOR_IMAGE_TAG env variable to a specific image "
            "to ensure that you are using a compatible version. "
            f"Check https://${self._get_emulator_image().replace('public.ecr', 'gallery.ecr')}. "
            "and https://github.com/aws/aws-durable-execution-sdk-python-testing/releases "
            "for valid image tags. If the problems persist, you can try updating the SAM CLI version "
            " in case of incompatibility. "
            "You may check the emulator_data_dir for the durable-execution-emulator-{timestamp}.log file which "
            "contains the emulator logs. This may be useful for debugging."
        )
