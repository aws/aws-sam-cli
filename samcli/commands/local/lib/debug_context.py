"""
Information and debug options for a specific runtime.
"""

import json


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

    @staticmethod
    def get_debug_ctx(debug_context_file_name):
        if not debug_context_file_name:
            return None

        with open(debug_context_file_name, 'r') as fp:
            data = fp.read()
            contexts = []
            for ctx in json.loads(data):
                contexts.append(DebugContext.deserialize(ctx))
            return contexts
