import os
import shutil
import tempfile
import logging
import subprocess
import time
import re

from flask import Flask, request, Response
from threading import Thread
from collections import deque
from unittest import TestCase
from pathlib import Path
from werkzeug.serving import make_server

from samcli.cli.global_config import GlobalConfig
from samcli.cli.main import TELEMETRY_PROMPT
from tests.testing_utils import get_sam_command

LOG = logging.getLogger(__name__)
TELEMETRY_ENDPOINT_PORT = "18298"
TELEMETRY_ENDPOINT_HOST = "localhost"
TELEMETRY_ENDPOINT_URL = "http://{}:{}".format(TELEMETRY_ENDPOINT_HOST, TELEMETRY_ENDPOINT_PORT)

# Convert line separators to work with Windows \r\n
EXPECTED_TELEMETRY_PROMPT = re.sub(r"\n", os.linesep, TELEMETRY_PROMPT)


class IntegBase(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cmd = get_sam_command()

    def setUp(self):
        self.maxDiff = None  # Show full JSON Diff

        self.config_dir = tempfile.mkdtemp()
        self._gc = GlobalConfig()
        self._gc.config_dir = Path(self.config_dir)

    def tearDown(self):
        self.config_dir and shutil.rmtree(self.config_dir)

    def run_cmd(self, cmd_list=None, stdin_data="", optout_envvar_value=None):
        # Any command will work for this test suite
        cmd_list = cmd_list or [self.cmd, "local", "generate-event", "s3", "put"]

        env = os.environ.copy()

        # remove the envvar which usually is set in CI/CD. This interferes with tests
        env.pop("SAM_CLI_TELEMETRY", None)
        if optout_envvar_value:
            # But if the caller explicitly asked us to opt-out via EnvVar, then set it here
            env["SAM_CLI_TELEMETRY"] = optout_envvar_value

        env["__SAM_CLI_APP_DIR"] = self.config_dir
        env["__SAM_CLI_TELEMETRY_ENDPOINT_URL"] = "{}/metrics".format(TELEMETRY_ENDPOINT_URL)

        process = subprocess.Popen(
            cmd_list, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env
        )
        return process

    def unset_config(self):
        config_file = Path(self.config_dir, "metadata.json")
        if config_file.exists():
            config_file.unlink()

    def set_config(self, telemetry_enabled=None):
        self._gc.telemetry_enabled = telemetry_enabled

    def get_global_config(self):
        return self._gc


class TelemetryServer:
    """
    HTTP Server that can receive and store Telemetry requests. Caller can later retrieve the responses for
    assertion

    Examples
    --------
    >>> with TelemetryServer() as server:
    >>>     # Server is running now
    >>>     # Set the Telemetry backend endpoint to the server's URL
    >>>     env = os.environ.copy().setdefault("__SAM_CLI_TELEMETRY_ENDPOINT_URL", server.url)
    >>>     # Run SAM CLI command
    >>>     p = subprocess.Popen(["samdev", "local", "generate-event", "s3", "put"], env=env)
    >>>     p.wait()  # Wait for process to complete
    >>>     # Get the first metrics request that was sent
    >>>     r = server.get_request(0)
    >>>     assert r.method == 'POST'
    >>>     assert r.body == "{...}"
    """

    def __init__(self):
        super().__init__()

        self.flask_app = Flask(__name__)

        self.flask_app.add_url_rule(
            "/metrics",
            endpoint="/metrics",
            view_func=self._request_handler,
            methods=["POST"],
            provide_automatic_options=False,
        )

        # Thread-safe data structure to record requests sent to the server
        self._requests = deque()

    def __enter__(self):
        self.server = make_server(TELEMETRY_ENDPOINT_HOST, TELEMETRY_ENDPOINT_PORT, self.flask_app)
        self.thread = Thread(target=self.server.serve_forever)
        self.thread.daemon = True  # When test completes, this thread will die automatically
        self.thread.start()  # Start the thread

        return self

    def __exit__(self, *args, **kwargs):
        # Flask will start shutting down only *after* the above request completes.
        # Just give the server a little bit of time to teardown finish
        time.sleep(2)

        self.server.shutdown()
        self.thread.join()

    def get_request(self, index):
        return self._requests[index]

    def get_all_requests(self):
        return list(self._requests)

    def _request_handler(self, **kwargs):
        """
        Handles Flask requests
        """

        # `request` is a variable populated by Flask automatically when handler method is called
        request_data = {
            "endpoint": request.endpoint,
            "method": request.method,
            "data": request.get_json(),
            "headers": dict(request.headers),
        }

        self._requests.append(request_data)

        return Response(response={}, status=200)
