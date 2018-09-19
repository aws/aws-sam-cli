"""
Reads CLI arguments and performs necessary preparation to be able to run the function
"""

import errno
import json
import sys
import os
import yaml

import docker
import requests

from samcli.yamlhelper import yaml_parse
from samcli.commands.local.lib.local_lambda import LocalLambdaRunner
from samcli.commands.local.lib.debug_context import DebugContext
from samcli.local.lambdafn.runtime import LambdaRuntime
from samcli.local.docker.manager import ContainerManager
from .user_exceptions import InvokeContextException, DebugContextException
from ..lib.sam_function_provider import SamFunctionProvider

# This is an attempt to do a controlled import. pathlib is in the
# Python standard library starting at 3.4. This will import pathlib2,
# which is a backport of the Python Standard Library pathlib
try:
    from pathlib import Path
except ImportError:
    from pathlib2 import Path


class InvokeContext(object):
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

    def __init__(self,
                 template_file,
                 function_identifier=None,
                 env_vars_file=None,
                 docker_volume_basedir=None,
                 docker_network=None,
                 log_file=None,
                 skip_pull_image=None,
                 aws_profile=None,
                 debug_port=None,
                 debug_args=None,
                 debugger_path=None,
                 aws_region=None,
                 parameter_overrides=None):
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
        debug_port int
            Port to bind the debugger to
        debug_args str
            Additional arguments passed to the debugger
        debugger_path str
            Path to the directory of the debugger to mount on Docker
        aws_profile str
            AWS Credential profile to use
        aws_region str
            AWS region to use
        parameter_overrides dict
            Values for the template parameters

        """
        self._template_file = template_file
        self._function_identifier = function_identifier
        self._env_vars_file = env_vars_file
        self._docker_volume_basedir = docker_volume_basedir
        self._docker_network = docker_network
        self._log_file = log_file
        self._skip_pull_image = skip_pull_image
        self._aws_profile = aws_profile
        self._aws_region = aws_region
        self._debug_port = debug_port
        self._debug_args = debug_args
        self._debugger_path = debugger_path
        self._parameter_overrides = parameter_overrides or {}

        self._template_dict = None
        self._function_provider = None
        self._env_vars_value = None
        self._log_file_handle = None
        self._debug_context = None

    def __enter__(self):
        """
        Performs some basic checks and returns itself when everything is ready to invoke a Lambda function.

        :returns InvokeContext: Returns this object
        """

        # Grab template from file and create a provider
        self._template_dict = self._get_template_data(self._template_file)
        self._function_provider = SamFunctionProvider(self._template_dict, self.parameter_overrides)

        self._env_vars_value = self._get_env_vars_value(self._env_vars_file)
        self._log_file_handle = self._setup_log_file(self._log_file)

        self._debug_context = self._get_debug_context(self._debug_port,
                                                      self._debug_args,
                                                      self._debugger_path)

        self._check_docker_connectivity()

        return self

    def __exit__(self, *args):
        """
        Cleanup any necessary opened files
        """

        if self._log_file_handle:
            self._log_file_handle.close()
            self._log_file_handle = None

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

        all_functions = [f for f in self._function_provider.get_all()]
        if len(all_functions) == 1:
            return all_functions[0].name

        # Get all the available function names to print helpful exception message
        all_function_names = [f.name for f in all_functions]

        # There are more functions in the template, and function identifier is not provided, hence raise.
        raise InvokeContextException("You must provide a function identifier (function's Logical ID in the template). "
                                     "Possible options in your template: {}".format(all_function_names))

    @property
    def local_lambda_runner(self):
        """
        Returns an instance of the runner capable of running Lambda functions locally

        :return samcli.commands.local.lib.local_lambda.LocalLambdaRunner: Runner configured to run Lambda functions
            locally
        """

        container_manager = ContainerManager(docker_network_id=self._docker_network,
                                             skip_pull_image=self._skip_pull_image)

        lambda_runtime = LambdaRuntime(container_manager)
        return LocalLambdaRunner(local_runtime=lambda_runtime,
                                 function_provider=self._function_provider,
                                 cwd=self.get_cwd(),
                                 env_vars_values=self._env_vars_value,
                                 debug_context=self._debug_context,
                                 aws_profile=self._aws_profile,
                                 aws_region=self._aws_region)

    @property
    def stdout(self):
        """
        Returns a stdout stream to output Lambda function logs to

        :return File like object: Stream where the output of the function is sent to
        """
        if self._log_file_handle:
            return self._log_file_handle

        # We write all of the data to stdout with bytes, typically io.BytesIO. stdout in Python2
        # accepts bytes but Python3 does not. This is due to a type change on the attribute. To keep
        # this consistent, we leave Python2 the same and get the .buffer attribute on stdout in Python3
        byte_stdout = sys.stdout

        if sys.version_info.major > 2:
            byte_stdout = sys.stdout.buffer  # pylint: disable=no-member

        return byte_stdout

    @property
    def stderr(self):
        """
        Returns stderr stream to output Lambda function errors to

        :return File like object: Stream where the stderr of the function is sent to
        """
        if self._log_file_handle:
            return self._log_file_handle

        # We write all of the data to stdout with bytes, typically io.BytesIO. stderr in Python2
        # accepts bytes but Python3 does not. This is due to a type change on the attribute. To keep
        # this consistent, we leave Python2 the same and get the .buffer attribute on stderr in Python3
        byte_stderr = sys.stderr

        if sys.version_info.major > 2:
            byte_stderr = sys.stderr.buffer  # pylint: disable=no-member

        return byte_stderr

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

    @staticmethod
    def _get_template_data(template_file):
        """
        Read the template file, parse it as JSON/YAML and return the template as a dictionary.

        :param string template_file: Path to the template to read
        :return dict: Template data as a dictionary
        :raises InvokeContextException: If template file was not found or the data was not a JSON/YAML
        """

        if not os.path.exists(template_file):
            raise InvokeContextException("Template file not found at {}".format(template_file))

        with open(template_file, 'r') as fp:
            try:
                return yaml_parse(fp.read())
            except (ValueError, yaml.YAMLError) as ex:
                raise InvokeContextException("Failed to parse template: {}".format(str(ex)))

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

            with open(filename, 'r') as fp:
                return json.load(fp)

        except Exception as ex:
            raise InvokeContextException("Could not read environment variables overrides from file {}: {}".format(
                                         filename,
                                         str(ex)))

    @staticmethod
    def _setup_log_file(log_file):
        """
        Open a log file if necessary and return the file handle. This will create a file if it does not exist

        :param string log_file: Path to a file where the logs should be written to
        :return: Handle to the opened log file, if necessary. None otherwise
        """
        if not log_file:
            return None

        return open(log_file, 'wb')

    @staticmethod
    def _get_debug_context(debug_port, debug_args, debugger_path):
        """
        Creates a DebugContext if the InvokeContext is in a debugging mode

        Parameters
        ----------
        debug_port int
             Port to bind the debugger to
        debug_args str
            Additional arguments passed to the debugger
        debugger_path str
            Path to the directory of the debugger to mount on Docker

        Returns
        -------
        samcli.commands.local.lib.debug_context.DebugContext
            Object representing the DebugContext

        Raises
        ------
        samcli.commands.local.cli_common.user_exceptions.DebugContext
            When the debugger_path is not valid
        """
        if debug_port and debugger_path:
            try:
                debugger = Path(debugger_path).resolve(strict=True)
            except OSError as error:
                if error.errno == errno.ENOENT:
                    raise DebugContextException("'{}' could not be found.".format(debugger_path))
                else:
                    raise error

            # We turn off pylint here due to https://github.com/PyCQA/pylint/issues/1660
            if not debugger.is_dir():  # pylint: disable=no-member
                raise DebugContextException("'{}' should be a directory with the debugger in it.".format(debugger_path))
            debugger_path = str(debugger)

        return DebugContext(debug_port=debug_port, debug_args=debug_args, debugger_path=debugger_path)

    @staticmethod
    def _check_docker_connectivity(docker_client=None):
        """
        Checks if Docker daemon is running. This is required for us to invoke the function locally

        :param docker_client: Instance of Docker client
        :return bool: True, if Docker is available
        :raises InvokeContextException: If Docker is not available
        """

        docker_client = docker_client or docker.from_env()

        try:
            docker_client.ping()
        # When Docker is not installed, a request.exceptions.ConnectionError is thrown.
        except (docker.errors.APIError, requests.exceptions.ConnectionError):
            raise InvokeContextException("Running AWS SAM projects locally requires Docker. Have you got it installed?")
