"""
Classes representing a local Lambda runtime
"""
import copy
import os
import shutil
import tempfile
import signal
import logging
import threading
from typing import Optional, Union, Dict

from samcli.local.docker.lambda_container import LambdaContainer
from samcli.lib.utils.file_observer import LambdaFunctionObserver
from samcli.lib.utils.packagetype import ZIP
from samcli.lib.telemetry.metric import capture_parameter
from .zip import unzip
from ...lib.providers.provider import LayerVersion
from ...lib.utils.stream_writer import StreamWriter

LOG = logging.getLogger(__name__)


class LambdaRuntime:
    """
    This class represents a Local Lambda runtime. It can run the Lambda function code locally in a Docker container
    and return results. Public methods exposed by this class are similar to the AWS Lambda APIs, for convenience only.
    This class is **not** intended to be an local replica of the Lambda APIs.
    """

    SUPPORTED_ARCHIVE_EXTENSIONS = (".zip", ".jar", ".ZIP", ".JAR")

    def __init__(self, container_manager, image_builder):
        """
        Initialize the Local Lambda runtime

        Parameters
        ----------
        container_manager samcli.local.docker.manager.ContainerManager
            Instance of the ContainerManager class that can run a local Docker container
        image_builder samcli.local.docker.lambda_image.LambdaImage
            Instance of the LambdaImage class that can create am image
        """
        self._container_manager = container_manager
        self._image_builder = image_builder
        self._temp_uncompressed_paths_to_be_cleaned = []

    def create(self, function_config, debug_context=None, container_host=None, container_host_interface=None):
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

        Returns
        -------
        Container
            the created container
        """
        # Generate a dictionary of environment variable key:values
        env_vars = function_config.env_vars.resolve()

        code_dir = self._get_code_dir(function_config.code_abs_path)
        layers = [self._unarchived_layer(layer) for layer in function_config.layers]
        container = LambdaContainer(
            function_config.runtime,
            function_config.imageuri,
            function_config.handler,
            function_config.packagetype,
            function_config.imageconfig,
            code_dir,
            layers,
            self._image_builder,
            function_config.architecture,
            memory_mb=function_config.memory,
            env_vars=env_vars,
            debug_options=debug_context,
            container_host=container_host,
            container_host_interface=container_host_interface,
            function_full_path=function_config.full_path,
        )
        try:
            # create the container.
            self._container_manager.create(container)
            return container

        except KeyboardInterrupt:
            LOG.debug("Ctrl+C was pressed. Aborting container creation")
            raise

    def run(self, container, function_config, debug_context, container_host=None, container_host_interface=None):
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

        Returns
        -------
        Container
            the running container
        """

        if not container:
            container = self.create(function_config, debug_context, container_host, container_host_interface)

        if container.is_running():
            LOG.info("Lambda function '%s' is already running", function_config.full_path)
            return container

        try:
            # start the container.
            self._container_manager.run(container)
            return container

        except KeyboardInterrupt:
            LOG.debug("Ctrl+C was pressed. Aborting container running")
            raise

    @capture_parameter("runtimeMetric", "runtimes", 1, parameter_nested_identifier="runtime", as_list=True)
    def invoke(
        self,
        function_config,
        event,
        debug_context=None,
        stdout: Optional[StreamWriter] = None,
        stderr: Optional[StreamWriter] = None,
        container_host=None,
        container_host_interface=None,
    ):
        """
        Invoke the given Lambda function locally.

        ##### NOTE: THIS IS A LONG BLOCKING CALL #####
        This method will block until either the Lambda function completes or timed out, which could be seconds.
        A blocking call will block the thread preventing any other operations from happening. If you are using this
        method in a web-server or in contexts where your application needs to be responsive when function is running,
        take care to invoke the function in a separate thread. Co-Routines or micro-threads might not perform well
        because the underlying implementation essentially blocks on a socket, which is synchronous.

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
        :raises Keyboard
        """
        timer = None
        container = None
        try:
            # Start the container. This call returns immediately after the container starts
            container = self.create(function_config, debug_context, container_host, container_host_interface)
            container = self.run(container, function_config, debug_context)
            # Setup appropriate interrupt - timeout or Ctrl+C - before function starts executing.
            #
            # Start the timer **after** container starts. Container startup takes several seconds, only after which,
            # our Lambda function code will run. Starting the timer is a reasonable approximation that function has
            # started running.
            timer = self._configure_interrupt(
                function_config.full_path, function_config.timeout, container, bool(debug_context)
            )

            # NOTE: BLOCKING METHOD
            # Block on waiting for result from the init process on the container, below method also
            # starts another thread to stream logs. This method will terminate
            # either successfully or be killed by one of the interrupt handlers above.
            container.wait_for_result(full_path=function_config.full_path, event=event, stdout=stdout, stderr=stderr)

        except KeyboardInterrupt:
            # When user presses Ctrl+C, we receive a Keyboard Interrupt. This is especially very common when
            # container is in debugging mode. We have special handling of Ctrl+C. So handle KeyboardInterrupt
            # and swallow the exception. The ``finally`` block will also take care of cleaning it up.
            LOG.debug("Ctrl+C was pressed. Aborting Lambda execution")

        finally:
            # We will be done with execution, if either the execution completed or an interrupt was fired
            # Any case, cleanup the timer and container.
            #
            # If we are in debugging mode, timer would not be created. So skip cleanup of the timer
            if timer:
                timer.cancel()
            self._on_invoke_done(container)

    def _on_invoke_done(self, container):
        """
        Cleanup the created resources, just before the invoke function ends

        Parameters
        ----------
        container: Container
           The current running container
        """
        if container:
            self._container_manager.stop(container)
        self._clean_decompressed_paths()

    def _configure_interrupt(self, function_full_path, timeout, container, is_debugging):
        """
        When a Lambda function is executing, we setup certain interrupt handlers to stop the execution.
        Usually, we setup a function timeout interrupt to kill the container after timeout expires. If debugging though,
        we don't enforce a timeout. But we setup a SIGINT interrupt to catch Ctrl+C and terminate the container.

        :param string function_full_path: The function full pth we are running
        :param integer timeout: Timeout in seconds
        :param samcli.local.docker.container.Container container: Instance of a container to terminate
        :param bool is_debugging: Are we debugging?
        :return threading.Timer: Timer object, if we setup a timer. None otherwise
        """

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

        # Start a timer, we'll use this to abort the function if it runs beyond the specified timeout
        LOG.debug("Starting a timer for %s seconds for function '%s'", timeout, function_full_path)
        timer = threading.Timer(timeout, timer_handler, ())
        timer.start()
        return timer

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
        for decompressed_dir in self._temp_uncompressed_paths_to_be_cleaned:
            shutil.rmtree(decompressed_dir)
        self._temp_uncompressed_paths_to_be_cleaned = []


class WarmLambdaRuntime(LambdaRuntime):
    """
    This class extends the LambdaRuntime class to add the Warm containers feature. This class handles the
    warm containers life cycle.
    """

    def __init__(self, container_manager, image_builder):
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

        self._observer = LambdaFunctionObserver(self._on_code_change)

        super().__init__(container_manager, image_builder)

    def create(self, function_config, debug_context=None, container_host=None, container_host_interface=None):
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

        # reuse the cached container if it is created, and if the function configuration is not changed
        exist_function_config = self._function_configs.get(function_config.full_path, None)
        container = self._containers.get(function_config.full_path, None)
        if exist_function_config and _require_container_reloading(exist_function_config, function_config):
            LOG.info(
                "Lambda Function '%s' definition has been changed in the stack template, "
                "terminate the created warm container.",
                function_config.full_path,
            )
            self._function_configs.pop(exist_function_config.full_path, None)
            if container:
                self._container_manager.stop(container)
                self._containers.pop(exist_function_config.full_path, None)
            self._observer.unwatch(exist_function_config)
        elif container and container.is_created():
            LOG.info("Reuse the created warm container for Lambda function '%s'", function_config.full_path)
            return container

        # debug_context should be used only if the function name is the one defined
        # in debug-function option
        if debug_context and debug_context.debug_function != function_config.name:
            LOG.debug(
                "Disable the debugging for Lambda Function %s, as the passed debug function is %s",
                function_config.name,
                debug_context.debug_function,
            )
            debug_context = None

        self._observer.watch(function_config)
        self._observer.start()

        container = super().create(function_config, debug_context, container_host, container_host_interface)
        self._function_configs[function_config.full_path] = function_config
        self._containers[function_config.full_path] = container

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

        # Start a timer, we'll use this to abort the function if it runs beyond the specified timeout
        LOG.debug("Starting a timer for %s seconds for function '%s'", timeout, function_full_path)
        timer = threading.Timer(timeout, timer_handler, ())
        timer.start()
        return timer

    def clean_running_containers_and_related_resources(self):
        """
        Clean the running containers, the decompressed code dirs, and stop the created observer
        """
        LOG.debug("Terminating all running warm containers")
        for function_name, container in self._containers.items():
            LOG.debug("Terminate running warm container for Lambda Function '%s'", function_name)
            self._container_manager.stop(container)
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
