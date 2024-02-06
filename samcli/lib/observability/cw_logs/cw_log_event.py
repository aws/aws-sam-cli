"""
CloudWatch log event type
"""

from typing import Optional

from samcli.lib.observability.observability_info_puller import ObservabilityEvent


class CWLogEvent(ObservabilityEvent[dict]):
    """
    An event class which represents a Cloud Watch log
    """

    def __init__(self, cw_log_group: str, event: dict, resource_name: Optional[str] = None):
        """
        Parameters
        ----------
        cw_log_group : str
            Name of the CloudWatch log group
        event : dict
            Event dictionary of the CloudWatch log event
        resource_name : Optional[str]
            Resource name that is related to this CloudWatch log event
        """
        self.cw_log_group = cw_log_group
        self.message: str = event.get("message", "")
        self.log_stream_name: str = event.get("logStreamName", "")
        timestamp: int = event.get("timestamp", 0)
        super().__init__(event, timestamp, resource_name)

    def __eq__(self, other):
        if not isinstance(other, CWLogEvent):
            return False

        return (
            self.cw_log_group == other.cw_log_group
            and self.log_stream_name == other.log_stream_name
            and self.timestamp == other.timestamp
            and self.message == other.message
        )
