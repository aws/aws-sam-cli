"""
Information and debug options for a specific runtime.
"""
import os


class DebugContext(object):

    def __init__(self,
                 debug_port=None,
                 debugger_path=None,
                 debug_args=None):

        self.debug_port = debug_port
        self.debugger_path = debugger_path
        self.debug_args = debug_args
        if self.debug_port:
            os.environ["PYTHONUNBUFFERED"] = "1"

    def __bool__(self):
        return bool(self.debug_port)

    def __nonzero__(self):
        return self.__bool__()
