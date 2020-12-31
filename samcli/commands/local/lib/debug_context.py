"""
Information and debug options for a specific runtime.
"""


class DebugContext:
    def __init__(
        self, debug_ports=None, debugger_path=None, debug_args=None, debug_function=None, container_env_vars=None
    ):
        """
        Initialize the Debug Context with Lambda debugger options

        :param tuple(int) debug_ports: Collection of debugger ports to be exposed from a docker container
        :param Path debugger_path: Path to a debugger to be launched
        :param string debug_args: Additional arguments to be passed to the debugger
        :param string debug_function: The Lambda function logicalId that will have the debugging options enabled in case
        of warm containers option is enabled
        :param dict container_env_vars: Additional environmental variables to be set.
        """

        self.debug_ports = debug_ports
        self.debugger_path = debugger_path
        self.debug_args = debug_args
        self.debug_function = debug_function
        self.container_env_vars = container_env_vars

    def __bool__(self):
        return bool(self.debug_ports)

    def __nonzero__(self):
        return self.__bool__()
