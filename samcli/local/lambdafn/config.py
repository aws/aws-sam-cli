"""
Lambda Function configuration data required by the runtime
"""
from samcli.commands.local.cli_common.user_exceptions import InvalidSamTemplateException
from .env_vars import EnvironmentVariables


class FunctionConfig:
    """
    Data class to store function configuration. This class is a flavor of function configuration passed to
    AWS Lambda APIs on the cloud. It is limited to properties that make sense in a local testing environment.
    """

    _DEFAULT_TIMEOUT_SECONDS = 3
    _DEFAULT_MEMORY = 128

    def __init__(
        self,
        name,
        runtime,
        handler,
        imageuri,
        imageconfig,
        packagetype,
        code_abs_path,
        layers,
        memory=None,
        timeout=None,
        env_vars=None,
    ):
        """
        Initialize the class.

        Parameters
        ----------
        name str
            Name of the function
        runtime str
            Runtime of function
        handler str
            Handler method
        code_abs_path str
            Absolute path to the code
        layers list(str)
            List of Layers
        memory int
            Function memory limit in MB
        timeout int
            Function timeout in seconds
        env_vars samcli.local.lambdafn.env_vars.EnvironmentVariables
            Optional, Environment variables.
            If it not provided, this class will generate one for you based on the function properties
        """
        self.name = name
        self.runtime = runtime
        self.imageuri = imageuri
        self.imageconfig = imageconfig
        self.packagetype = packagetype
        self.handler = handler
        self.code_abs_path = code_abs_path
        self.layers = layers
        self.memory = memory or self._DEFAULT_MEMORY

        self.timeout = timeout or self._DEFAULT_TIMEOUT_SECONDS

        if not isinstance(self.timeout, int):
            try:
                self.timeout = int(self.timeout)

            except (ValueError, TypeError) as ex:
                raise InvalidSamTemplateException("Invalid Number for Timeout: {}".format(self.timeout)) from ex

        if not env_vars:
            env_vars = EnvironmentVariables(self.memory, self.timeout, self.handler)

        self.env_vars = env_vars
        # Re-apply memory & timeout because those could have been set to default values
        self.env_vars.handler = self.handler
        self.env_vars.memory = self.memory
        self.env_vars.timeout = self.timeout

    def __eq__(self, other):
        return self.name == other.name
