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

    def __eq__(self, other):
        """
        Compare two DebugContext instances for equality.

        Parameters
        ----------
        other : DebugContext or None
            Other debug context to compare with

        Returns
        -------
        bool
            True if both debug contexts have the same configuration
        """
        if not isinstance(other, DebugContext):
            return False

        return (
            self.debug_ports == other.debug_ports
            and self.debugger_path == other.debugger_path
            and self.debug_args == other.debug_args
            and self.debug_function == other.debug_function
            and self.container_env_vars == other.container_env_vars
        )

    def __hash__(self):
        """
        Make DebugContext hashable so it can be used in sets/dicts.

        Returns
        -------
        int
            Hash value based on debug context attributes
        """
        return hash(
            (
                self.debug_ports,
                str(self.debugger_path) if self.debugger_path else None,
                self.debug_args,
                self.debug_function,
                tuple(sorted(self.container_env_vars.items())) if self.container_env_vars else None,
            )
        )
