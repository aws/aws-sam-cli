"""
Classes representing a local Lambda runtime
"""

import copy
import logging
import os
import shutil
import signal
import tempfile
import threading
from typing import Dict, Optional, Union

from samcli.lib.telemetry.metric import capture_parameter
from samcli.lib.utils.file_observer import LambdaFunctionObserver
from samcli.lib.utils.packagetype import ZIP
from samcli.local.docker.container import Container, ContainerContext
from samcli.local.docker.container_analyzer import ContainerAnalyzer
from samcli.local.docker.durable_functions_emulator_container import DurableFunctionsEmulatorContainer
from samcli.local.docker.durable_lambda_container import DurableLambdaContainer
from samcli.local.docker.exceptions import ContainerFailureError, DockerContainerCreationFailedException
from samcli.local.docker.lambda_container import LambdaContainer
from samcli.local.lambdafn.exceptions import UnsupportedInvocationType

from ...lib.providers.provider import LayerVersion
from ...lib.utils.stream_writer import StreamWriter
from .zip import unzip

LOG = logging.getLogger(__name__)


class LambdaRuntime:
    """
    This class represents a Local Lambda runtime. It can run the Lambda function code locally in a Docker container
    and return results. Public methods exposed by this class are similar to the AWS Lambda APIs, for convenience only.
    This class is **not** intended to be an local replica of the Lambda APIs.
    """

    SUPPORTED_ARCHIVE_EXTENSIONS = (".zip", ".jar", ".ZIP", ".JAR")

    def __init__(self, container_manager, image_builder, mount_symlinks=False, no_mem_limit=False):
        """
        Initialize the Local Lambda runtime

        Parameters
        ----------
        container_manager samcli.local.docker.manager.ContainerManager
            Instance of the ContainerManager class that can run a local Docker container
        image_builder samcli.local.docker.lambda_image.LambdaImage
            Instance of the LambdaImage class that can create am image
        mount_symlinks bool
            Optional. True is symlinks should be mounted in the container
        """
        self._container_manager = container_manager
        self._container = None  # Track current container
        self._image_builder = image_builder
        self._temp_uncompressed_paths_to_be_cleaned = []
        self._lock = threading.Lock()
        self._mount_symlinks = mount_symlinks
        self._no_mem_limit = no_mem_limit

        """
        Reference to an instance of the durable executions emulator container. Each instance of a lambda runtime may 
        have an emulator container created (if the runtime is for a durable function), however, we implement a 
        reattachment mechanism so that each instance is using the same underlying container.
        """
        self._durable_execution_emulator_container = None

    def create(
        self,
        function_config,
        debug_context=None,
        container_host=None,
        container_host_interface=None,
        extra_hosts=None,
    ):
        """
        Create a new Container for the passed function, then store it in a dictionary using the function name,
        so it can be retrieved later and used in the other functions. Make sure to use the debug_context only
        if the function_config.name equals debug_context.debug-function or the warm_containers option is disabled

        Parameters
        ----------
        function_config FunctionConfig
            Configuration of the function to create a new Container for it.
        debug_context DebugContext
            Debugging context for the function (includes port, args, and path)
        container_host string
            Host of locally emulated Lambda container
        container_host_interface string
            Optional. Interface that Docker host binds ports to
        extra_hosts Dict
            Optional. Dict of hostname to IP resolutions

        Returns
        -------
        Container
            the created container
        """
        # Generate a dictionary of environment variable key:values
        env_vars = function_config.env_vars.resolve()

        code_dir = self._get_code_dir(function_config.code_abs_path)
        layers = [self._unarchived_layer(layer) for layer in function_config.layers]
        if function_config.runtime_management_config and function_config.runtime_management_config.get(
            "RuntimeVersionArn"
        ):
            sam_accelerate_link = "https://s12d.com/accelerate"
            LOG.info(
                "This function will be invoked using the latest available runtime, which may differ from your "
                "Runtime Management Configuration. To test this function with a pinned runtime, test on AWS with "
                "`sam sync -–help`. Learn more here: %s",
                sam_accelerate_link,
            )

        container_args = (
            function_config.runtime,
            function_config.imageuri,
            function_config.handler,
            function_config.packagetype,
            function_config.imageconfig,
            code_dir,
            layers,
            self._image_builder,
            function_config.architecture,
        )

        container_kwargs = {
            "memory_mb": None if self._no_mem_limit else function_config.memory,
            "env_vars": env_vars,
            "debug_options": debug_context,
            "container_host": container_host,
            "container_host_interface": container_host_interface,
            "extra_hosts": extra_hosts,
            "function_full_path": function_config.full_path,
            "mount_symlinks": self._mount_symlinks,
        }

        # Check if this is a durable function and create appropriate container type
        if function_config.durable_config:
            emulator_container = self.get_or_create_emulator_container()
            is_warm_runtime = isinstance(self, WarmLambdaRuntime)
            container = DurableLambdaContainer(
                *container_args,
                emulator_container=emulator_container,
                durable_config=function_config.durable_config,
                is_warm_runtime=is_warm_runtime,
                **container_kwargs,
            )
        else:
            container = LambdaContainer(*container_args, **container_kwargs)

        self._container = container

        try:
            # create the container.
            self._container_manager.create(container, ContainerContext.INVOKE)
            return container

        except DockerContainerCreationFailedException:
            LOG.warning("Failed to create container for function %s", function_config.full_path)
            raise

        except KeyboardInterrupt:
            LOG.debug("Ctrl+C was pressed. Aborting container creation")
            raise

    def run(
        self,
        container,
        function_config,
        debug_context,
        container_host=None,
        container_host_interface=None,
        extra_hosts=None,
    ):
        """
        Find the created container for the passed Lambda function, then using the
        ContainerManager run this container.
        If the Container is not created, it will create it first then start it.

        Parameters
        ----------
        container Container
            the created container to be run
        function_config FunctionConfig
            Configuration of the function to run its created container.
        debug_context DebugContext
            Debugging context for the function (includes port, args, and path)
        container_host string
            Host of locally emulated Lambda container
        container_host_interface string
            Optional. Interface that Docker host binds ports to
        extra_hosts Dict
            Optional. Dict of hostname to IP resolutions

        Returns
        -------
        Container
            the running container
        """

        if not container:
            container = self.create(
                function_config=function_config,
                debug_context=debug_context,
                container_host=container_host,
                container_host_interface=container_host_interface,
                extra_hosts=extra_hosts,
            )

        if container.is_running():
            LOG.info("Lambda function '%s' is already running", function_config.full_path)
            return container

        try:
            # start the container.
            self._container_manager.run(container, ContainerContext.INVOKE)
            return container

        except KeyboardInterrupt:
            LOG.debug("Ctrl+C was pressed. Aborting container running")
            raise

    @capture_parameter("runtimeMetric", "runtimes", 1, parameter_nested_identifier="runtime", as_list=True)
    def invoke(
        self,
        function_config,
        event,
        tenant_id=None,
        invocation_type: str = "RequestResponse",
        durable_execution_name: Optional[str] = None,
        debug_context=None,
        stdout: Optional[StreamWriter] = None,
        stderr: Optional[StreamWriter] = None,
        container_host=None,
        container_host_interface=None,
        extra_hosts=None,
    ) -> Optional[Dict[str, str]]:
        """
        Invoke the given Lambda function locally.

        ##### NOTE: THIS IS A LONG BLOCKING CALL #####
        This method will block until either the Lambda function completes or timed out, which could be seconds.
        A blocking call will block the thread preventing any other operations from happening. If you are using this
        method in a web-server or in contexts where your application needs to be responsive when function is running,
        take care to invoke the function in a separate thread. Co-Routines or micro-threads might not perform well
        because the underlying implementation essentially blocks on a socket, which is synchronous.

        Note: Concurrency control is now handled at the container level. Each container manages its own
        semaphore based on AWS_LAMBDA_MAX_CONCURRENCY environment variable.

        :param FunctionConfig function_config: Configuration of the function to invoke
        :param event: String input event passed to Lambda function
        :param DebugContext debug_context: Debugging context for the function (includes port, args, and path)
        :param samcli.lib.utils.stream_writer.StreamWriter stdout: Optional.
            StreamWriter that receives stdout text from container.
        :param samcli.lib.utils.stream_writer.StreamWriter stderr: Optional.
            StreamWriter that receives stderr text from container.
        :param string container_host: Optional.
            Host of locally emulated Lambda container
        :param string container_host_interface: Optional.
            Interface that Docker host binds ports to
        :param dict extra_hosts: Optional.
            Dict of hostname to IP resolutions
        :returns: Optional[Dict[str, str]]
            HTTP headers dict if this was a durable function invocation, None otherwise
        :raises Keyboard
        """
        container = None
        headers = None
        try:
            # Start the container. This call returns immediately after the container starts
            container = self.create(
                function_config, debug_context, container_host, container_host_interface, extra_hosts
            )
            container = self.run(
                container,
                function_config,
                debug_context,
                container_host,
                container_host_interface,
                extra_hosts,
            )
            # Setup appropriate interrupt - timeout or Ctrl+C - before function starts executing and
            # get callback function to start timeout timer
            start_timer = self._configure_interrupt(
                function_config.full_path, function_config.timeout, container, bool(debug_context)
            )

            # NOTE: BLOCKING METHOD
            # Block on waiting for result from the init process on the container, below method also
            # starts another thread to stream logs. This method will terminate
            # either successfully or be killed by one of the interrupt handlers above.

            if isinstance(container, DurableLambdaContainer):
                headers = container.wait_for_result(
                    full_path=function_config.full_path,
                    event=event,
                    stdout=stdout,
                    stderr=stderr,
                    start_timer=start_timer,
                    durable_execution_name=durable_execution_name,
                    invocation_type=invocation_type,
                )
            else:
                # Only RequestResponse supported for regular Lambda functions
                if invocation_type != "RequestResponse":
                    raise UnsupportedInvocationType(
                        f"invocation-type: {invocation_type} is not supported. RequestResponse is only supported."
                    )

                # The container handles concurrency control internally via its semaphore.
                container.wait_for_result(
                    full_path=function_config.full_path,
                    event=event,
                    stdout=stdout,
                    stderr=stderr,
                    start_timer=start_timer,
                    tenant_id=tenant_id,
                )

        except KeyboardInterrupt:
            # When user presses Ctrl+C, we receive a Keyboard Interrupt. This is especially very common when
            # container is in debugging mode. We have special handling of Ctrl+C. So handle KeyboardInterrupt
            # and swallow the exception. The ``finally`` block will also take care of cleaning it up.
            LOG.debug("Ctrl+C was pressed. Aborting Lambda execution")

        finally:
            # We will be done with execution, if either the execution completed or an interrupt was fired
            # Any case, cleanup the container.
            self._on_invoke_done(container)

        return headers

    def _on_invoke_done(self, container):
        """
        Cleanup the created resources, just before the invoke function ends

        Parameters
        ----------
        container: Container
           The current running container
        """
        if container:
            self._check_exit_state(container)
            self._container_manager.stop(container)
        self._clean_decompressed_paths()

    def _check_exit_state(self, container: Container):
        """
        Check and validate the exit state of the invoke container.

        Parameters
        ----------
        container: Container
            Docker container to be checked

        Raises
        -------
        ContainerFailureError
            If the exit reason is due to out-of-memory, return exit code 1

        """
        container_analyzer = ContainerAnalyzer(self._container_manager, container)
        exit_state = container_analyzer.inspect()
        if exit_state.out_of_memory:
            raise ContainerFailureError("Container invocation failed due to maximum memory usage")

    def _configure_interrupt(self, function_full_path, timeout, container, is_debugging):
        """
        When a Lambda function is executing, we setup certain interrupt handlers to stop the execution.
        Usually, we setup a function timeout interrupt to kill the container after timeout expires. If debugging though,
        we don't enforce a timeout. But we setup a SIGINT interrupt to catch Ctrl+C and terminate the container.

        :param string function_full_path: The function full pth we are running
        :param integer timeout: Timeout in seconds
        :param samcli.local.docker.container.Container container: Instance of a container to terminate
        :param bool is_debugging: Are we debugging?
        :return func: function to start timer, if we set one up. None otherwise
        """

        def start_timer():
            # Start a timer, we'll use this to abort the function if it runs beyond the specified timeout
            LOG.debug("Starting a timer for %s seconds for function '%s'", timeout, function_full_path)
            timer = threading.Timer(timeout, timer_handler, ())
            timer.start()
            return timer

        def timer_handler():
            # NOTE: This handler runs in a separate thread. So don't try to mutate any non-thread-safe data structures
            LOG.info("Function '%s' timed out after %d seconds", function_full_path, timeout)
            self._container_manager.stop(container)

        def signal_handler(sig, frame):
            # NOTE: This handler runs in a separate thread. So don't try to mutate any non-thread-safe data structures
            LOG.info("Execution of function %s was interrupted", function_full_path)
            self._container_manager.stop(container)

        if is_debugging:
            LOG.debug("Setting up SIGTERM interrupt handler")
            signal.signal(signal.SIGTERM, signal_handler)
            return None

        return start_timer

    def _get_code_dir(self, code_path: str) -> str:
        """
        Method to get a path to a directory where the function/layer code is available. This directory will
        be mounted directly inside the Docker container.

        This method handles a few different cases for ``code_path``:
            - ``code_path``is a existent zip/jar file: Unzip in a temp directory and return the temp directory
            - ``code_path`` is a existent directory: Return this immediately
            - ``code_path`` is a file/dir that does not exist: Return it as is. May be this method is not clever to
                detect the existence of the path

        Parameters
        ----------
        code_path: str
            Path to the code. This could be pointing at a file or folder either on a local
            disk or in some network file system

        Returns
        -------
        str
            Directory containing Lambda function code. It can be mounted directly in container
        """

        if code_path and os.path.isfile(code_path) and code_path.endswith(self.SUPPORTED_ARCHIVE_EXTENSIONS):
            decompressed_dir: str = _unzip_file(code_path)
            self._temp_uncompressed_paths_to_be_cleaned += [decompressed_dir]
            return decompressed_dir

        LOG.debug("Code %s is not a zip/jar file", code_path)
        return code_path

    def _unarchived_layer(self, layer: Union[str, Dict, LayerVersion]) -> Union[str, Dict, LayerVersion]:
        """
        If the layer's content uri points to a supported local archive file, use self._get_code_dir() to
        un-archive it and so that it can be mounted directly inside the Docker container.
        Parameters
        ----------
        layer
            a str, dict or a LayerVersion object representing a layer

        Returns
        -------
            as it is (if no archived file is identified)
            or a LayerVersion with ContentUri pointing to an unarchived directory
        """
        if isinstance(layer, LayerVersion) and isinstance(layer.codeuri, str):
            unarchived_layer = copy.deepcopy(layer)
            unarchived_layer.codeuri = self._get_code_dir(layer.codeuri)
            return unarchived_layer if unarchived_layer.codeuri != layer.codeuri else layer

        return layer

    def _clean_decompressed_paths(self):
        """
        Clean the temporary decompressed code dirs
        """
        LOG.debug("Cleaning all decompressed code dirs")
        with self._lock:
            for decompressed_dir in self._temp_uncompressed_paths_to_be_cleaned:
                shutil.rmtree(decompressed_dir)
            self._temp_uncompressed_paths_to_be_cleaned = []

    def get_or_create_emulator_container(self):
        """
        Get or create emulator container. Provides singleton behavior for all runtime types.

        Returns:
            DurableFunctionsEmulatorContainer: The singleton emulator container
        """
        if self._durable_execution_emulator_container is None:
            self._durable_execution_emulator_container = DurableFunctionsEmulatorContainer()
            self._durable_execution_emulator_container.start_or_attach()
            LOG.debug("Created and started durable functions emulator container")
        return self._durable_execution_emulator_container

    def clean_runtime_containers(self):
        """
        Clean up any containers created during the runtime which haven't already been cleaned.

        This is only used for durable executions since we defer the container management to
        the durable lambda container implementation. This method is a catch-all called from
        InvokeContext.__exit__ to ensure that we *always* cleanup the runtime container resources.
        """
        # Clean up lambda container
        if self._container and isinstance(self._container, DurableLambdaContainer):
            try:
                self._container._stop()
                self._container._delete()
            except Exception as e:
                LOG.error("Error stopping durable lambda container: %s", e)
            finally:
                self._container = None

        # Clean up durable execution emulator container
        if self._durable_execution_emulator_container:
            LOG.debug("Stopping durable functions emulator container")
            self._durable_execution_emulator_container.stop()
            self._durable_execution_emulator_container = None


class WarmLambdaRuntime(LambdaRuntime):
    """
    This class extends the LambdaRuntime class to add the Warm containers feature. This class handles the
    warm containers life cycle.
    """

    def __init__(self, container_manager, image_builder, observer=None, mount_symlinks=False, no_mem_limit=False):
        """
        Initialize the Local Lambda runtime

        Parameters
        ----------
        container_manager samcli.local.docker.manager.ContainerManager
            Instance of the ContainerManager class that can run a local Docker container
        image_builder samcli.local.docker.lambda_image.LambdaImage
            Instance of the LambdaImage class that can create am image
        warm_containers bool
            Determines if the warm containers is enabled or not.
        """
        self._function_configs = {}
        self._containers = {}
        self._container_lock = threading.Lock()  # Thread-safe container creation

        self._observer = observer if observer else LambdaFunctionObserver(self._on_code_change)

        super().__init__(container_manager, image_builder, mount_symlinks=mount_symlinks, no_mem_limit=no_mem_limit)

    def create(
        self,
        function_config,
        debug_context=None,
        container_host=None,
        container_host_interface=None,
        extra_hosts=None,
    ):
        """
        Create a new Container for the passed function, then store it in a dictionary using the function name,
        so it can be retrieved later and used in the other functions. Make sure to use the debug_context only
        if the function_config.name equals debug_context.debug-function or the warm_containers option is disabled

        Parameters
        ----------
        function_config FunctionConfig
            Configuration of the function to create a new Container for it.
        debug_context DebugContext
            Debugging context for the function (includes port, args, and path)
        container_host string
            Host of locally emulated Lambda container
        container_host_interface string
            Interface that Docker host binds ports to

        Returns
        -------
        Container
            the created container
        """

        # Thread-safe container check and creation
        with self._container_lock:
            function_path = function_config.full_path

            # Filter debug_context: only apply if this function is the debug target
            effective_debug_context = None
            if debug_context and debug_context.debug_function == function_config.name:
                effective_debug_context = debug_context

            # Check existing container and whether it needs reloading
            exist_function_config = self._function_configs.get(function_path, None)
            container = self._containers.get(function_path, None)

            # Check if we need to reload the container
            needs_reload = _should_reload_container(
                exist_function_config, function_config, container, effective_debug_context
            )

            if needs_reload:
                # Clean up existing container
                self._function_configs.pop(function_path, None)
                if container:
                    self._container_manager.stop(container)
                    self._containers.pop(function_path, None)
                if exist_function_config:
                    self._observer.unwatch(exist_function_config)
                container = None

            # Reuse existing container if available and compatible
            elif container and container.is_created():
                return container

            # Create new container
            self._observer.watch(function_config)
            self._observer.start()

            container = super().create(
                function_config, effective_debug_context, container_host, container_host_interface, extra_hosts
            )

            # Store container and config
            self._function_configs[function_path] = function_config
            self._containers[function_path] = container

            return container

    def _on_invoke_done(self, container):
        """
        Cleanup the created resources, just before the invoke function ends.
        In warm containers, the running containers will be closed just before the end of te command execution,
        so no action is done here

        Parameters
        ----------
        container: Container
           The current running container
        """

    def _configure_interrupt(self, function_full_path, timeout, container, is_debugging):
        """
        When a Lambda function is executing, we setup certain interrupt handlers to stop the execution.
        Usually, we setup a function timeout interrupt to kill the container after timeout expires. If debugging though,
        we don't enforce a timeout. But we setup a SIGINT interrupt to catch Ctrl+C and terminate the container.

        Parameters
        ----------
        function_full_path: str
            The function full path we are running
        timeout: int
            Timeout in seconds
        container: samcli.local.docker.container.Container
            Instance of a container to terminate
        is_debugging: bool
            Are we debugging?

        Returns
        -------
        threading.Timer
            Timer object, if we setup a timer. None otherwise
        """

        def start_timer():
            # Start a timer, we'll use this to abort the function if it runs beyond the specified timeout
            LOG.debug("Starting a timer for %s seconds for function '%s'", timeout, function_full_path)
            timer = threading.Timer(timeout, timer_handler, ())
            timer.start()
            return timer

        def timer_handler():
            # NOTE: This handler runs in a separate thread. So don't try to mutate any non-thread-safe data structures
            LOG.info("Function '%s' timed out after %d seconds", function_full_path, timeout)

        def signal_handler(sig, frame):
            # NOTE: This handler runs in a separate thread. So don't try to mutate any non-thread-safe data structures
            LOG.info("Execution of function %s was interrupted", function_full_path)

        if is_debugging:
            LOG.debug("Setting up SIGTERM interrupt handler")
            signal.signal(signal.SIGTERM, signal_handler)
            return None

        return start_timer

    def clean_running_containers_and_related_resources(self):
        """
        Clean the running containers, the decompressed code dirs, and stop the created observer
        """
        LOG.debug("Terminating all running warm containers")
        for function_name, container in self._containers.items():
            LOG.debug("Terminate running warm container for Lambda Function '%s'", function_name)
            self._container_manager.stop(container)

        # Clear all stored state
        self._containers.clear()
        self._function_configs.clear()

        self._clean_decompressed_paths()
        self._observer.stop()

    def _on_code_change(self, functions):
        """
        Handles the lambda function code change event. it determines if there is a real change in the code
        by comparing the checksum of the code path before and after the event.

        Parameters
        ----------
        functions: list [FunctionConfig]
            the lambda functions that their source code or images got changed
        """
        for function_config in functions:
            function_full_path = function_config.full_path
            resource = "source code" if function_config.packagetype == ZIP else f"{function_config.imageuri} image"
            LOG.info(
                "Lambda Function '%s' %s has been changed, terminate its warm container. "
                "The new container will be created in lazy mode",
                function_full_path,
                resource,
            )
            self._observer.unwatch(function_config)
            self._function_configs.pop(function_full_path, None)
            container = self._containers.get(function_full_path, None)
            if container:
                self._container_manager.stop(container)
                self._containers.pop(function_full_path, None)


def _unzip_file(filepath):
    """
    Helper method to unzip a file to a temporary directory

    :param string filepath: Absolute path to this file
    :return string: Path to the temporary directory where it was unzipped
    """

    temp_dir = tempfile.mkdtemp()

    if os.name == "posix":
        os.chmod(temp_dir, 0o755)

    LOG.info("Decompressing %s", filepath)

    unzip(filepath, temp_dir)

    # The directory that Python returns might have symlinks. The Docker File sharing settings will not resolve
    # symlinks. Hence get the real path before passing to Docker.
    # Especially useful in Mac OSX which returns /var/folders which is a symlink to /private/var/folders that is a
    # part of Docker's Shared Files directories
    return os.path.realpath(temp_dir)


def _require_container_reloading(exist_function_config, function_config):
    return (
        exist_function_config.runtime != function_config.runtime
        or exist_function_config.handler != function_config.handler
        or exist_function_config.packagetype != function_config.packagetype
        or exist_function_config.imageuri != function_config.imageuri
        or exist_function_config.imageconfig != function_config.imageconfig
        or exist_function_config.code_abs_path != function_config.code_abs_path
        or exist_function_config.env_vars != function_config.env_vars
        or sorted(exist_function_config.layers, key=lambda x: x.full_path)
        != sorted(function_config.layers, key=lambda x: x.full_path)
    )


def _should_reload_container(exist_function_config, function_config, container, effective_debug_context):
    """
    Determine if a container needs to be reloaded based on configuration changes or debug context changes.

    Parameters
    ----------
    exist_function_config : FunctionConfig or None
        The existing function configuration, if any
    function_config : FunctionConfig
        The new function configuration
    container : Container or None
        The existing container, if any
    effective_debug_context : DebugContext or None
        The effective debug context for this function

    Returns
    -------
    bool
        True if the container needs to be reloaded, False otherwise
    """
    # Check if function configuration has changed
    if exist_function_config and _require_container_reloading(exist_function_config, function_config):
        return True

    # Check if debug context has changed
    if container and container.debug_options != effective_debug_context:
        return True

    return False
