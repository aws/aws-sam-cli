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
        full_path,
        runtime,
        handler,
        imageuri,
        imageconfig,
        packagetype,
        code_abs_path,
        layers,
        architecture,
        memory=None,
        timeout=None,
        runtime_management_config=None,
        env_vars=None,
        code_real_path=None,
    ):
        """
        Parameters
        ----------
        name : str
            Name of the function
        full_path : str
            The function full path
        runtime : str
            Runtime of function
        handler : str
            Handler method
        imageuri : str
            Location of the Lambda Image which is of the form {image}:{tag}, sha256:{digest},
            or a path to a local archive
        imageconfig : str
            Image configuration which can be used set to entrypoint, command and working dir for the container.
        packagetype : str
            Package type for the lambda function which is either zip or image.
        code_abs_path : str
            Absolute path to the code
        layers : list(str)
            List of Layers
        architecture : str
            Architecture type either x86_64 or arm64 on AWS lambda
        memory : int, optional
            Function memory limit in MB, by default None
        timeout : int, optional
            Function timeout in seconds, by default None
        runtime_management_config: str, optional
            Function's runtime management config
        env_vars : str, optional
            Environment variables, by default None
             If it not provided, this class will generate one for you based on the function properties

        Raises
        ------
        InvalidSamTemplateException
            Throw when template provided was invalid and not able to transform into a Standard CloudFormation Template
        """

        self.name = name
        self.full_path = full_path
        self.runtime = runtime
        self.imageuri = imageuri
        self.imageconfig = imageconfig
        self.packagetype = packagetype
        self.handler = handler
        self.code_abs_path = code_abs_path
        self.code_real_path = code_real_path
        self.layers = layers
        self.memory = memory or self._DEFAULT_MEMORY
        self.architecture = architecture

        self.timeout = timeout or self._DEFAULT_TIMEOUT_SECONDS
        self.runtime_management_config = runtime_management_config

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
        return self.full_path == other.full_path
