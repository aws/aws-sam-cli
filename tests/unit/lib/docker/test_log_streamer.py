from unittest import TestCase

from samcli.lib.utils.stream_writer import StreamWriter
from samcli.lib.utils.osutils import stderr
from samcli.lib.docker.log_streamer import LogStreamer


from docker.errors import APIError


class TestLogStreamer(TestCase):
    def setUp(self):
        self.stream = StreamWriter(stream=stderr(), auto_flush=True)
        self.error_class = APIError
        self.image = "image:v1"

    def test_logstreamer_init(self):
        LogStreamer(stream=self.stream)

    def test_logstreamer_stream_progress(self):
        log_streamer = LogStreamer(stream=self.stream)
        log_streamer.stream_progress(
            iter(
                [
                    {"status": "Pushing to xyz"},
                    {"id": "1", "status": "Preparing", "progress": ""},
                    {"id": "2", "status": "Preparing", "progress": ""},
                    {"id": "3", "status": "Preparing", "progress": ""},
                    {"id": "1", "status": "Pushing", "progress": "[====>   ]"},
                    {"id": "3", "status": "Pushing", "progress": "[====>   ]"},
                    {"id": "2", "status": "Pushing", "progress": "[====>   ]"},
                    {"id": "3", "status": "Pushed", "progress": "[========>]"},
                    {"id": "1", "status": "Pushed", "progress": "[========>]"},
                    {"id": "2", "status": "Pushed", "progress": "[========>]"},
                    {"status": f"image {self.image} pushed digest: a89q34f"},
                    {},
                ]
            )
        )
