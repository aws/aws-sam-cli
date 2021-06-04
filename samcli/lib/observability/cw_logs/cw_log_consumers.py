"""
Contains consumers of CloudWatch log events.

Only CWConsoleEventConsumer is inside 'samcli.commdans.logs.console_consumers' since
click library is not allowed in lib folder
"""
import json
import os
import time
import uuid
from typing import Optional, Any

from samcli.lib.observability.cw_logs.cw_log_event import CWLogEvent
from samcli.lib.observability.observability_info_puller import ObservabilityEventConsumer


class CWFileEventConsumer(ObservabilityEventConsumer):
    """
    Stores each consumed event in the given file. File can be setup by providing its folder, and its
    prefix. Rest of the file name will contain timestamp.
    """

    def __init__(self, output_dir: str, file_prefix: Optional[str] = None):
        """
        Parameters
        ----------
        output_dir : str
            Location of the folder which file will be stored in
        file_prefix : Optional[str]
            Optional file prefix parameter for the filename. Auto generated UUID will be used in case nothing is given
        """
        super().__init__()
        if file_prefix:
            file_name = f"{file_prefix}-{time.time()}.log"
        else:
            file_name = f"{uuid.uuid4()}-{time.time()}.log"
        self.file_name = os.path.join(output_dir, file_name)

    def consume(self, event: Any):
        message = event
        if isinstance(event, CWLogEvent):
            message = f"{json.dumps(event.event)}\n"
        with open(self.file_name, "a+") as handle:
            handle.write(message)
