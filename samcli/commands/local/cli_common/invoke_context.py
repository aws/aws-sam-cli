"""
Reads CLI arguments and performs necessary preparation to be able to run the function
"""
import errno
import json
import logging
import os
from enum import Enum
from pathlib import Path

import samcli.lib.utils.osutils as osutils
from samcli.lib.utils.async_utils import AsyncContext
from samcli.lib.utils.stream_writer import StreamWriter
from samcli.commands.local.lib.local_lambda import LocalLambdaRunner
from samcli.commands.local.lib.debug_context import DebugContext
from samcli.local.lambdafn.runtime import LambdaRuntime, WarmLambdaRuntime
from samcli.local.docker.lambda_image import LambdaImage
from samcli.local.docker.manager import ContainerManager
from samcli.commands._utils.template import get_template_data, TemplateNotFoundException, TemplateFailedParsingException
from samcli.local.layers.layer_downloader import LayerDownloader
from samcli.lib.providers.sam_function_provider import SamFunctionProvider
from .user_exceptions import InvokeContextException, DebugContextException
from ...exceptions import ContainersInitializationException

LOG = logging.getLogger(__name__)


class ContainersInitializationMode(Enum):
    EAGER = "EAGER"
    LAZY = "LAZY"


class ContainersMode(Enum):
    WARM = "WARM"
    COLD = "COLD"


class InvokeContext:
    """
    Sets up a context to invoke Lambda functions locally by parsing all command line arguments necessary for the
    invoke.

    ``start-api`` command will also use this class to read and parse invoke related CLI arguments and setup the
    necessary context to invoke.

    This class *must* be used inside a `with` statement as follows:

        with InvokeContext(**kwargs) as context:
            context.local_lambda_runner.invoke(...)

    This class sets up some resources that need to be cleaned up after the context object is used.
    """

    def __init__(
        self,  # pylint: disable=R0914
        template_file,
        function_identifier=None,
        env_vars_file=None,
        docker_volume_basedir=None,
        docker_network=None,
        log_file=None,
        skip_pull_image=None,
        debug_ports=None,
        debug_args=None,
        debugger_path=None,
        container_env_vars_file=None,
        parameter_overrides=None,
        layer_cache_basedir=None,
        force_image_build=None,
        aws_region=None,
        aws_profile=None,
        warm_container_initialization_mode=None,
        debug_function=None,
        shutdown=False,
    ):
        """
        Initialize the context

        Parameters
        ----------
        template_file str
            Name or path to template
        function_identifier str
            Identifier of the function to invoke
        env_vars_file str
            Path to a file containing values for environment variables
        docker_volume_basedir str
            Directory for the Docker volume
        docker_network str
            Docker network identifier
        log_file str
            Path to a file to send container output to. If the file does not exist, it will be
            created
        skip_pull_image bool
            Should we skip pulling the Docker container image?
        aws_profile str
            Name of the profile to fetch AWS credentials from
        debug_ports tuple(int)
            Ports to bind the debugger to
        debug_args str
            Additional arguments passed to the debugger
        debugger_path str
            Path to the directory of the debugger to mount on Docker
        parameter_overrides dict
            Values for the template parameters
        layer_cache_basedir str
            String representing the path to the layer cache directory
        force_image_build bool
            Whether or not to force build the image
        aws_region str
            AWS region to use
        warm_container_initialization_mode str
            Specifies how SAM cli manages the containers when using start-api or start_lambda.
            Two modes are available:
            "EAGER": Containers for every function are loaded at startup and persist between invocations.
            "LAZY": Containers are only loaded when the function is first invoked and persist for additional invocations
        debug_function str
            The Lambda function logicalId that will have the debugging options enabled in case of warm containers
            option is enabled
        shutdown bool
            Optional. If True, perform a SHUTDOWN event when tearing down containers. Default False.
        """
        self._template_file = template_file
        self._function_identifier = function_identifier
        self._env_vars_file = env_vars_file
        self._docker_volume_basedir = docker_volume_basedir
        self._docker_network = docker_network
        self._log_file = log_file
        self._skip_pull_image = skip_pull_image
        self._debug_ports = debug_ports
        self._debug_args = debug_args
        self._debugger_path = debugger_path
        self._container_env_vars_file = container_env_vars_file
        self._parameter_overrides = parameter_overrides or {}
        self._layer_cache_basedir = layer_cache_basedir
        self._force_image_build = force_image_build
        self._aws_region = aws_region
        self._aws_profile = aws_profile
        self._shutdown = shutdown

        self._containers_mode = ContainersMode.COLD
        self._containers_initializing_mode = ContainersInitializationMode.LAZY

        if warm_container_initialization_mode:
            self._containers_mode = ContainersMode.WARM
            self._containers_initializing_mode = ContainersInitializationMode(warm_container_initialization_mode)

        self._debug_function = debug_function

        self._template_dict = None
        self._function_provider = None
        self._env_vars_value = None
        self._container_env_vars_value = None
        self._log_file_handle = None
        self._debug_context = None
        self._layers_downloader = None
        self._container_manager = None
        self._lambda_runtimes = None

        self._local_lambda_runner = None

    def __enter__(self):
        """
        Performs some basic checks and returns itself when everything is ready to invoke a Lambda function.

        :returns InvokeContext: Returns this object
        """

        # Grab template from file and create a provider
        self._template_dict = self._get_template_data(self._template_file)
        self._function_provider = SamFunctionProvider(self._template_dict, self.parameter_overrides)

        self._env_vars_value = self._get_env_vars_value(self._env_vars_file)
        self._container_env_vars_value = self._get_env_vars_value(self._container_env_vars_file)
        self._log_file_handle = self._setup_log_file(self._log_file)

        # in case of warm containers && debugging is enabled && if debug-function property is not provided, so
        # if the provided template only contains one lambda function, so debug-function will be set to this function
        # if the template contains multiple functions, a warning message "that the debugging option will be ignored"
        # will be printed
        if self._containers_mode == ContainersMode.WARM and self._debug_ports and not self._debug_function:
            if len(self._function_provider.functions) == 1:
                self._debug_function = list(self._function_provider.functions.keys())[0]
            else:
                LOG.info(
                    "Warning: you supplied debugging options but you did not specify the --debug-function option."
                    " To specify which function you want to debug, please use the --debug-function <function-name>"
                )
                # skipp the debugging
                self._debug_ports = None

        self._debug_context = self._get_debug_context(
            self._debug_ports,
            self._debug_args,
            self._debugger_path,
            self._container_env_vars_value,
            self._debug_function,
        )

        self._container_manager = self._get_container_manager(
            self._docker_network, self._skip_pull_image, self._shutdown
        )

        if not self._container_manager.is_docker_reachable:
            raise InvokeContextException(
                "Running AWS SAM projects locally requires Docker. Have you got it installed and running?"
            )

        # initialize all lambda function containers upfront
        if self._containers_initializing_mode == ContainersInitializationMode.EAGER:
            self._initialize_all_functions_containers()

        return self

    def __exit__(self, *args):
        """
        Cleanup any necessary opened resources
        """

        if self._log_file_handle:
            self._log_file_handle.close()
            self._log_file_handle = None

        if self._containers_mode == ContainersMode.WARM:
            self._clean_running_containers_and_related_resources()

    def _initialize_all_functions_containers(self):
        """
        Create and run a container for each available lambda function
        """
        LOG.info("Initializing the lambda functions containers.")

        def initialize_function_container(function):
            function_config = self.local_lambda_runner.get_invoke_config(function)
            self.lambda_runtime.run(None, function_config, self._debug_context)

        try:
            async_context = AsyncContext()
            for function in self._function_provider.get_all():
                async_context.add_async_task(initialize_function_container, function)

            async_context.run_async(default_executor=False)
            LOG.info("Containers Initialization is done.")
        except KeyboardInterrupt:
            LOG.debug("Ctrl+C was pressed. Aborting containers initialization")
            self._clean_running_containers_and_related_resources()
            raise
        except Exception as ex:
            LOG.error("Lambda functions containers initialization failed because of %s", ex)
            self._clean_running_containers_and_related_resources()
            raise ContainersInitializationException("Lambda functions containers initialization failed") from ex

    def _clean_running_containers_and_related_resources(self):
        """
        Clean the running containers and any other related open resources
        """
        self.lambda_runtime.clean_running_containers_and_related_resources()

    @property
    def function_name(self):
        """
        Returns name of the function to invoke. If no function identifier is provided, this method will return name of
        the only function from the template

        :return string: Name of the function
        :raises InvokeContextException: If function identifier is not provided
        """
        if self._function_identifier:
            return self._function_identifier

        # Function Identifier is *not* provided. If there is only one function in the template,
        # default to it.

        all_functions = list(self._function_provider.get_all())
        if len(all_functions) == 1:
            return all_functions[0].functionname

        # Get all the available function names to print helpful exception message
        all_function_names = [f.functionname for f in all_functions]

        # There are more functions in the template, and function identifier is not provided, hence raise.
        raise InvokeContextException(
            "You must provide a function identifier (function's Logical ID in the template). "
            "Possible options in your template: {}".format(all_function_names)
        )

    @property
    def lambda_runtime(self):
        if not self._lambda_runtimes:
            layer_downloader = LayerDownloader(self._layer_cache_basedir, self.get_cwd())
            image_builder = LambdaImage(layer_downloader, self._skip_pull_image, self._force_image_build)
            self._lambda_runtimes = {
                ContainersMode.WARM: WarmLambdaRuntime(self._container_manager, image_builder),
                ContainersMode.COLD: LambdaRuntime(self._container_manager, image_builder),
            }

        return self._lambda_runtimes[self._containers_mode]

    @property
    def local_lambda_runner(self):
        """
        Returns an instance of the runner capable of running Lambda functions locally

        :return samcli.commands.local.lib.local_lambda.LocalLambdaRunner: Runner configured to run Lambda functions
            locally
        """
        if self._local_lambda_runner:
            return self._local_lambda_runner

        self._local_lambda_runner = LocalLambdaRunner(
            local_runtime=self.lambda_runtime,
            function_provider=self._function_provider,
            cwd=self.get_cwd(),
            aws_profile=self._aws_profile,
            aws_region=self._aws_region,
            env_vars_values=self._env_vars_value,
            debug_context=self._debug_context,
        )
        return self._local_lambda_runner

    @property
    def stdout(self):
        """
        Returns stream writer for stdout to output Lambda function logs to

        Returns
        -------
        samcli.lib.utils.stream_writer.StreamWriter
            Stream writer for stdout
        """
        stream = self._log_file_handle if self._log_file_handle else osutils.stdout()
        return StreamWriter(stream, self._is_debugging)

    @property
    def stderr(self):
        """
        Returns stream writer for stderr to output Lambda function errors to

        Returns
        -------
        samcli.lib.utils.stream_writer.StreamWriter
            Stream writer for stderr
        """
        stream = self._log_file_handle if self._log_file_handle else osutils.stderr()
        return StreamWriter(stream, self._is_debugging)

    @property
    def template(self):
        """
        Returns the template data as dictionary

        :return dict: Template data
        """
        return self._template_dict

    def get_cwd(self):
        """
        Get the working directory. This is usually relative to the directory that contains the template. If a Docker
        volume location is specified, it takes preference

        All Lambda function code paths are resolved relative to this working directory

        :return string: Working directory
        """

        cwd = os.path.dirname(os.path.abspath(self._template_file))
        if self._docker_volume_basedir:
            cwd = self._docker_volume_basedir

        return cwd

    @property
    def parameter_overrides(self):
        # Override certain CloudFormation pseudo-parameters based on values provided by customer
        if self._aws_region:
            self._parameter_overrides["AWS::Region"] = self._aws_region

        return self._parameter_overrides

    @property
    def _is_debugging(self):
        return bool(self._debug_context)

    @staticmethod
    def _get_template_data(template_file):
        """
        Read the template file, parse it as JSON/YAML and return the template as a dictionary.

        :param string template_file: Path to the template to read
        :return dict: Template data as a dictionary
        :raises InvokeContextException: If template file was not found or the data was not a JSON/YAML
        """

        try:
            return get_template_data(template_file)
        except (TemplateNotFoundException, TemplateFailedParsingException) as ex:
            raise InvokeContextException(str(ex)) from ex

    @staticmethod
    def _get_env_vars_value(filename):
        """
        If the user provided a file containing values of environment variables, this method will read the file and
        return its value

        :param string filename: Path to file containing environment variable values
        :return dict: Value of environment variables, if provided. None otherwise
        :raises InvokeContextException: If the file was not found or not a valid JSON
        """
        if not filename:
            return None

        # Try to read the file and parse it as JSON
        try:

            with open(filename, "r") as fp:
                return json.load(fp)

        except Exception as ex:
            raise InvokeContextException(
                "Could not read environment variables overrides from file {}: {}".format(filename, str(ex))
            ) from ex

    @staticmethod
    def _setup_log_file(log_file):
        """
        Open a log file if necessary and return the file handle. This will create a file if it does not exist

        :param string log_file: Path to a file where the logs should be written to
        :return: Handle to the opened log file, if necessary. None otherwise
        """
        if not log_file:
            return None

        return open(log_file, "wb")

    @staticmethod
    def _get_debug_context(debug_ports, debug_args, debugger_path, container_env_vars, debug_function=None):
        """
        Creates a DebugContext if the InvokeContext is in a debugging mode

        Parameters
        ----------
        debug_ports tuple(int)
             Ports to bind the debugger to
        debug_args str
            Additional arguments passed to the debugger
        debugger_path str
            Path to the directory of the debugger to mount on Docker
        container_env_vars dict
            Dictionary containing debugging based environmental variables.
        debug_function str
            The Lambda function logicalId that will have the debugging options enabled in case of warm containers
            option is enabled

        Returns
        -------
        samcli.commands.local.lib.debug_context.DebugContext
            Object representing the DebugContext

        Raises
        ------
        samcli.commands.local.cli_common.user_exceptions.DebugContext
            When the debugger_path is not valid
        """
        if debug_ports and debugger_path:
            try:
                debugger = Path(debugger_path).resolve(strict=True)
            except OSError as error:
                if error.errno == errno.ENOENT:
                    raise DebugContextException("'{}' could not be found.".format(debugger_path)) from error

                raise error

            if not debugger.is_dir():
                raise DebugContextException("'{}' should be a directory with the debugger in it.".format(debugger_path))
            debugger_path = str(debugger)

        return DebugContext(
            debug_ports=debug_ports,
            debug_args=debug_args,
            debugger_path=debugger_path,
            debug_function=debug_function,
            container_env_vars=container_env_vars,
        )

    @staticmethod
    def _get_container_manager(docker_network, skip_pull_image, shutdown):
        """
        Creates a ContainerManager with specified options

        Parameters
        ----------
        docker_network str
            Docker network identifier
        skip_pull_image bool
            Should the manager skip pulling the image
        shutdown bool
            Should SHUTDOWN events be sent when tearing down image

        Returns
        -------
        samcli.local.docker.manager.ContainerManager
            Object representing Docker container manager
        """

        return ContainerManager(
            docker_network_id=docker_network, skip_pull_image=skip_pull_image, do_shutdown_event=shutdown
        )
