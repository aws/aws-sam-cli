"""
Implementation of Local Lambda runner
"""

import os
import logging
from typing import Any, Dict, Optional, cast
import boto3

from botocore.credentials import Credentials

from samcli.commands.local.lib.debug_context import DebugContext
from samcli.lib.providers.sam_function_provider import SamFunctionProvider
from samcli.lib.utils.codeuri import resolve_code_path
from samcli.lib.utils.packagetype import ZIP, IMAGE
from samcli.lib.utils.stream_writer import StreamWriter
from samcli.local.docker.container import ContainerResponseException
from samcli.local.lambdafn.env_vars import EnvironmentVariables
from samcli.local.lambdafn.config import FunctionConfig
from samcli.local.lambdafn.exceptions import FunctionNotFound
from samcli.commands.local.lib.exceptions import InvalidIntermediateImageError
from samcli.commands.local.lib.exceptions import OverridesNotWellDefinedError, NoPrivilegeException
from samcli.lib.providers.provider import Function
from samcli.local.lambdafn.runtime import LambdaRuntime

LOG = logging.getLogger(__name__)


class LocalLambdaRunner:
    """
    Runs Lambda functions locally. This class is a wrapper around the `samcli.local` library which takes care
    of actually running the function on a Docker container.
    """

    MAX_DEBUG_TIMEOUT = 36000  # 10 hours in seconds

    def __init__(
        self,
        local_runtime: LambdaRuntime,
        function_provider: SamFunctionProvider,
        cwd: str,
        aws_profile: Optional[str] = None,
        aws_region: Optional[str] = None,
        env_vars_values: Optional[Dict[Any, Any]] = None,
        debug_context: Optional[DebugContext] = None,
        container_host: Optional[str] = None,
        container_host_interface: Optional[str] = None,
    ) -> None:
        """
        Initializes the class

        :param samcli.local.lambdafn.runtime.LambdaRuntime local_runtime: Lambda runtime capable of running a function
        :param samcli.commands.local.lib.provider.FunctionProvider function_provider: Provider that can return a
            Lambda function
        :param string cwd: Current working directory. We will resolve all function CodeURIs relative to this directory.
        :param string aws_profile: Optional. Name of the profile to fetch AWS credentials from.
        :param string aws_region: Optional. AWS Region to use.
        :param dict env_vars_values: Optional. Dictionary containing values of environment variables.
        :param DebugContext debug_context: Optional. Debug context for the function (includes port, args, and path).
        :param string container_host: Optional. Host of locally emulated Lambda container
        :param string container_host_interface: Optional. Interface that Docker host binds ports to
        """

        self.local_runtime = local_runtime
        self.provider = function_provider
        self.cwd = cwd
        self.aws_profile = aws_profile
        self.aws_region = aws_region
        self.env_vars_values = env_vars_values or {}
        self.debug_context = debug_context
        self._boto3_session_creds: Optional[Dict[str, str]] = None
        self._boto3_region: Optional[str] = None
        self.container_host = container_host
        self.container_host_interface = container_host_interface

    def invoke(
        self,
        function_identifier: str,
        event: str,
        stdout: Optional[StreamWriter] = None,
        stderr: Optional[StreamWriter] = None,
    ) -> None:
        """
        Find the Lambda function with given name and invoke it. Pass the given event to the function and return
        response through the given streams.

        This function will block until either the function completes or times out.

        Parameters
        ----------
        function_identifier str
            Identifier of the Lambda function to invoke, it can be logicalID, function name or full path
        event str
            Event data passed to the function. Must be a valid JSON String.
        stdout samcli.lib.utils.stream_writer.StreamWriter
            Stream writer to write the output of the Lambda function to.
        stderr samcli.lib.utils.stream_writer.StreamWriter
            Stream writer to write the Lambda runtime logs to.

        Raises
        ------
        FunctionNotfound
            When we cannot find a function with the given name
        """

        # Generate the correct configuration based on given inputs
        function = self.provider.get(function_identifier)

        if not function:
            all_function_full_paths = [f.full_path for f in self.provider.get_all()]
            available_function_message = "{} not found. Possible options in your template: {}".format(
                function_identifier, all_function_full_paths
            )
            LOG.info(available_function_message)
            raise FunctionNotFound("Unable to find a Function with name '{}'".format(function_identifier))

        LOG.debug("Found one Lambda function with name '%s'", function_identifier)
        if function.packagetype == ZIP:
            LOG.info("Invoking %s (%s)", function.handler, function.runtime)
        elif function.packagetype == IMAGE:
            if not function.imageuri:
                raise InvalidIntermediateImageError(
                    f"ImageUri not provided for Function: {function_identifier} of PackageType: {function.packagetype}"
                )
            LOG.info("Invoking Container created from %s", function.imageuri)
        config = self.get_invoke_config(function)

        # Invoke the function
        try:
            self.local_runtime.invoke(
                config,
                event,
                debug_context=self.debug_context,
                stdout=stdout,
                stderr=stderr,
                container_host=self.container_host,
                container_host_interface=self.container_host_interface,
            )
        except ContainerResponseException:
            # NOTE(sriram-mv): This should still result in a exit code zero to avoid regressions.
            LOG.info("No response from invoke container for %s", function.name)
        except OSError as os_error:
            # pylint: disable=no-member
            if hasattr(os_error, "winerror") and os_error.winerror == 1314:  # type: ignore
                raise NoPrivilegeException(
                    "Administrator, Windows Developer Mode, "
                    "or SeCreateSymbolicLinkPrivilege is required to create symbolic link for files: {}, {}".format(
                        os_error.filename, os_error.filename2
                    )
                ) from os_error

            raise

    def is_debugging(self) -> bool:
        """
        Are we debugging the invoke?

        Returns
        -------
        bool
            True, if we are debugging the invoke ie. the Docker container will break into the debugger and wait for
            attach
        """
        return bool(self.debug_context)

    def get_invoke_config(self, function: Function) -> FunctionConfig:
        """
        Returns invoke configuration to pass to Lambda Runtime to invoke the given function

        :param samcli.commands.local.lib.provider.Function function: Lambda function to generate the configuration for
        :return samcli.local.lambdafn.config.FunctionConfig: Function configuration to pass to Lambda runtime
        """

        env_vars = self._make_env_vars(function)
        code_abs_path = None
        if function.packagetype == ZIP:
            code_abs_path = resolve_code_path(self.cwd, function.codeuri)
            LOG.debug("Resolved absolute path to code is %s", code_abs_path)

        function_timeout = function.timeout

        # The Runtime container handles timeout inside the container. When debugging with short timeouts, this can
        # cause the container execution to stop. When in debug mode, we set the timeout in the container to a max 10
        # hours. This will ensure the container doesn't unexpectedly stop while debugging function code
        if self.is_debugging():
            function_timeout = self.MAX_DEBUG_TIMEOUT

        return FunctionConfig(
            name=function.name,
            runtime=function.runtime,
            handler=function.handler,
            imageuri=function.imageuri,
            imageconfig=function.imageconfig,
            packagetype=function.packagetype,
            code_abs_path=code_abs_path,
            layers=function.layers,
            memory=function.memory,
            timeout=function_timeout,
            env_vars=env_vars,
        )

    def _make_env_vars(self, function: Function) -> EnvironmentVariables:
        """Returns the environment variables configuration for this function

        Parameters
        ----------
        function : samcli.commands.local.lib.provider.Function
            Lambda function to generate the configuration for

        Returns
        -------
        samcli.local.lambdafn.env_vars.EnvironmentVariables
            Environment variable configuration for this function

        Raises
        ------
        samcli.commands.local.lib.exceptions.OverridesNotWellDefinedError
            If the environment dict is in the wrong format to process environment vars

        """

        name = function.name

        variables = None
        if isinstance(function.environment, dict) and "Variables" in function.environment:
            variables = function.environment["Variables"]
        else:
            LOG.debug("No environment variables found for function '%s'", name)

        # This could either be in standard format, or a CloudFormation parameter file format.
        #
        # Standard format is {FunctionName: {key:value}, FunctionName: {key:value}}
        # CloudFormation parameter file is {"Parameters": {key:value}}

        for env_var_value in self.env_vars_values.values():
            if not isinstance(env_var_value, dict):
                reason = """
                            Environment variables must be in either CloudFormation parameter file
                            format or in {FunctionName: {key:value}} JSON pairs
                            """
                LOG.debug(reason)
                raise OverridesNotWellDefinedError(reason)

        if "Parameters" in self.env_vars_values:
            LOG.debug("Environment variables overrides data is in CloudFormation parameter file format")
            # CloudFormation parameter file format
            overrides = self.env_vars_values["Parameters"]
        else:
            # Standard format
            LOG.debug("Environment variables overrides data is standard format")
            overrides = self.env_vars_values.get(name, None)

        shell_env = os.environ
        aws_creds = self.get_aws_creds()

        return EnvironmentVariables(
            function.name,
            function.memory,
            function.timeout,
            function.handler,
            variables=variables,
            shell_env_values=shell_env,
            override_values=overrides,
            aws_creds=aws_creds,
        )  # EnvironmentVariables is not yet annotated with type hints, disable mypy check for now. type: ignore

    def _get_session_creds(self) -> Credentials:
        if self._boto3_session_creds is None:
            # to pass command line arguments for region & profile to setup boto3 default session
            LOG.debug("Loading AWS credentials from session with profile '%s'", self.aws_profile)
            # The signature of boto3.session.Session defines the default values of profile_name and region_name
            # so they should be Optional. But mypy follows its docstring which does not have "Optional."
            # Here we trick mypy thinking they are both str rather than Optional[str].
            session = boto3.session.Session(
                profile_name=cast(str, self.aws_profile), region_name=cast(str, self.aws_region)
            )

            # check for region_name in session and cache
            if hasattr(session, "region_name") and session.region_name:
                self._boto3_region = session.region_name

            # don't set cached session creds if there is not a session
            if session:
                self._boto3_session_creds = session.get_credentials()

        return self._boto3_session_creds

    def get_aws_creds(self) -> Dict[str, str]:
        """
        Returns AWS credentials obtained from the shell environment or given profile

        :return dict: A dictionary containing credentials. This dict has the structure
             {"region": "", "key": "", "secret": "", "sessiontoken": ""}. If credentials could not be resolved,
             this returns None
        """
        result: Dict[str, str] = {}

        # Load the credentials from profile/environment
        creds = self._get_session_creds()

        # After loading credentials, region name might be available here.
        if self._boto3_region:
            result["region"] = self._boto3_region

        if not creds:
            # If we were unable to load credentials, then just return result. We will use the default
            return result

        # Only add the key, if its value is present
        if hasattr(creds, "access_key") and creds.access_key:
            result["key"] = creds.access_key

        if hasattr(creds, "secret_key") and creds.secret_key:
            result["secret"] = creds.secret_key

        if hasattr(creds, "token") and creds.token:
            result["sessiontoken"] = creds.token

        return result
