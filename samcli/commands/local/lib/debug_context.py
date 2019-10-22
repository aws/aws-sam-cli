"""
Information and debug options for a specific runtime.
"""


class DebugContext(object):
    def __init__(self, debug_ports=None, debugger_path=None, debug_args=None):

        self.debug_ports = debug_ports
        self.debugger_path = debugger_path
        self.debug_args = debug_args

    def __bool__(self):
        return bool(self.debug_ports)

    def __nonzero__(self):
        return self.__bool__()
