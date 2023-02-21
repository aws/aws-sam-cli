"""
Class to publish metrics
"""

import logging

import requests

# Get the preconfigured endpoint URL
from samcli.cli.global_config import GlobalConfig
from samcli.settings import telemetry_endpoint_url as DEFAULT_ENDPOINT_URL

LOG = logging.getLogger(__name__)


class Telemetry:
    def __init__(self, url=None):
        """
        Initialize the Telemetry object.

        Parameters
        ----------
        url : str
            Optional, URL where the metrics should be published to
        """
        self._url = url or DEFAULT_ENDPOINT_URL
        LOG.debug("Telemetry endpoint configured to be %s", self._url)

    def emit(self, metric, force_emit=False):
        """
        Emits the metric with given name and the attributes and send it immediately to the HTTP backend. This method
        will return immediately without waiting for response from the backend. Before sending, this method will
        also update ``attrs`` with some common attributes used by all metrics.

        Parameters
        ----------
        metric : Metric
            Metric to be published

        force_emit : bool
            Defaults to False. Set to True to emit even when telemetry is turned off.
        """
        if bool(GlobalConfig().telemetry_enabled) or force_emit:
            self._send({metric.get_metric_name(): metric.get_data()})

    def _send(self, metric, wait_for_response=False):
        """
        Serializes the metric data to JSON and sends to the backend.

        Parameters
        ----------

        metric : dict
            Dictionary of metric data to send to backend.

        wait_for_response : bool
            If set to True, this method will wait until the HTTP server returns a response. If not, it will return
            immediately after the request is sent.
        """

        if not self._url:
            # Endpoint not configured. So simply return
            LOG.debug("Not sending telemetry. Endpoint URL not configured")
            return

        payload = {"metrics": [metric]}
        LOG.debug("Sending Telemetry: %s", payload)

        timeout_ms = 2000 if wait_for_response else 100  # 2 seconds to wait for response or 100ms

        timeout = (
            2,  # connection timeout. Always set to 2 seconds
            timeout_ms / 1000.0,  # Read timeout. Tweaked based on input.
        )
        try:
            r = requests.post(self._url, json=payload, timeout=timeout)
            LOG.debug("Telemetry response: %d", r.status_code)
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as ex:
            # Expected if request times out OR cannot connect to the backend (offline).
            # Just print debug log and ignore the exception.
            LOG.debug(str(ex))
