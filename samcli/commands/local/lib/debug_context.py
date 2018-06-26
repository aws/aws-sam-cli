"""
Information and debug options for a specific runtime.
"""


class DebugContext(object):

    def __init__(self,
                 debug_port=None,
                 runtime=None,
                 debugger_path=None,
                 debug_args=None):

        self.debug_port = debug_port
        self.runtime = runtime
        self.debugger_path = debugger_path
        self.debug_args = debug_args

    @staticmethod
    def deserialize(obj):
        debug_port = obj.get("debug_port", None)
        runtime = obj.get("runtime", None)
        debugger_path = obj.get("debugger_path", None)
        debug_args = obj.get("debug_args", None)
        return DebugContext(debug_port, runtime, debugger_path, debug_args)
