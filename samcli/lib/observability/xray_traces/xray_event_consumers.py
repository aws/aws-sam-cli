"""
Contains consumer implementations of XRay observability events
"""
import json
import os
import time
import uuid

from samcli.lib.observability.observability_info_puller import ObservabilityEventConsumer
from samcli.lib.observability.xray_traces.xray_events import XRayTraceEvent


class XRayEventFileConsumer(ObservabilityEventConsumer[XRayTraceEvent]):
    def __init__(self, output_dir: str):
        """
        Parameters
        ----------
        output_dir : str
            Location of the folder which file will be stored in
        """
        self.file_name = os.path.join(output_dir, f"{uuid.uuid4()}-{time.time()}.json")

    def consume(self, event: XRayTraceEvent):
        with open(self.file_name, "a+") as handle:
            handle.write(f"{json.dumps(event.event)}\n")
