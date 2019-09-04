import platform
import requests

from mock import patch, Mock, ANY
from unittest import TestCase

from samcli.lib.telemetry.telemetry import Telemetry
from samcli import __version__ as samcli_version


class TestTelemetry(TestCase):
    def setUp(self):
        self.test_session_id = "TestSessionId"
        self.test_installation_id = "TestInstallationId"
        self.url = "some_test_url"

        self.gc_mock = Mock()
        self.context_mock = Mock()

        self.global_config_patcher = patch("samcli.lib.telemetry.telemetry.GlobalConfig", self.gc_mock)
        self.context_patcher = patch("samcli.lib.telemetry.telemetry.Context", self.context_mock)

        self.global_config_patcher.start()
        self.context_patcher.start()

        self.context_mock.get_current_context.return_value.session_id = self.test_session_id
        self.gc_mock.return_value.installation_id = self.test_installation_id

    def tearDown(self):
        self.global_config_patcher.stop()
        self.context_mock.stop()

    def test_must_raise_on_invalid_session_id(self):
        self.context_mock.get_current_context.return_value = None

        with self.assertRaises(RuntimeError):
            Telemetry()

    @patch("samcli.lib.telemetry.telemetry.requests")
    def test_must_add_metric_with_attributes_to_registry(self, requests_mock):
        telemetry = Telemetry(url=self.url)
        metric_name = "mymetric"
        attrs = {"a": 1, "b": 2}

        telemetry.emit(metric_name, attrs)

        expected = {
            "metrics": [
                {
                    metric_name: {
                        "a": 1,
                        "b": 2,
                        "requestId": ANY,
                        "installationId": self.test_installation_id,
                        "sessionId": self.test_session_id,
                        "executionEnvironment": "CLI",
                        "pyversion": platform.python_version(),
                        "samcliVersion": samcli_version,
                    }
                }
            ]
        }
        requests_mock.post.assert_called_once_with(ANY, json=expected, timeout=ANY)

    @patch("samcli.lib.telemetry.telemetry.requests")
    @patch("samcli.lib.telemetry.telemetry.uuid")
    def test_must_add_request_id_as_uuid_v4(self, uuid_mock, requests_mock):
        fake_uuid = uuid_mock.uuid4.return_value = "fake uuid"

        telemetry = Telemetry(url=self.url)
        telemetry.emit("metric_name", {})

        expected = {"metrics": [{"metric_name": _ignore_other_attrs({"requestId": fake_uuid})}]}
        requests_mock.post.assert_called_once_with(ANY, json=expected, timeout=ANY)

    @patch("samcli.lib.telemetry.telemetry.requests")
    def test_execution_environment_should_be_identified(self, requests_mock):
        telemetry = Telemetry(url=self.url)

        telemetry.emit("metric_name", {})

        expected_execution_environment = "CLI"

        expected = {
            "metrics": [{"metric_name": _ignore_other_attrs({"executionEnvironment": expected_execution_environment})}]
        }
        requests_mock.post.assert_called_once_with(ANY, json=expected, timeout=ANY)

    @patch("samcli.lib.telemetry.telemetry.requests")
    def test_default_request_should_be_fire_and_forget(self, requests_mock):
        telemetry = Telemetry(url=self.url)

        telemetry.emit("metric_name", {})
        requests_mock.post.assert_called_once_with(ANY, json=ANY, timeout=(2, 0.1))  # 100ms response timeout

    @patch("samcli.lib.telemetry.telemetry.requests")
    def test_request_must_wait_for_2_seconds_for_response(self, requests_mock):
        telemetry = Telemetry(url=self.url)

        telemetry._send({}, wait_for_response=True)
        requests_mock.post.assert_called_once_with(ANY, json=ANY, timeout=(2, 2))

    @patch("samcli.lib.telemetry.telemetry.requests")
    def test_must_swallow_timeout_exception(self, requests_mock):
        telemetry = Telemetry(url=self.url)

        # If we Mock the entire requests library, this statement will run into issues
        #   `except requests.exceptions.Timeout`
        # https://stackoverflow.com/questions/31713054/cant-catch-mocked-exception-because-it-doesnt-inherit-baseexception
        #
        # Hence we save the original Timeout object to the Mock, so Python won't complain.
        #

        requests_mock.exceptions.Timeout = requests.exceptions.Timeout
        requests_mock.exceptions.ConnectionError = requests.exceptions.ConnectionError
        requests_mock.post.side_effect = requests.exceptions.Timeout()

        telemetry.emit("metric_name", {})

    @patch("samcli.lib.telemetry.telemetry.requests")
    def test_must_swallow_connection_error_exception(self, requests_mock):
        telemetry = Telemetry(url=self.url)

        requests_mock.exceptions.Timeout = requests.exceptions.Timeout
        requests_mock.exceptions.ConnectionError = requests.exceptions.ConnectionError
        requests_mock.post.side_effect = requests.exceptions.ConnectionError()

        telemetry.emit("metric_name", {})

    @patch("samcli.lib.telemetry.telemetry.requests")
    def test_must_raise_on_other_requests_exception(self, requests_mock):
        telemetry = Telemetry(url=self.url)

        requests_mock.exceptions.Timeout = requests.exceptions.Timeout
        requests_mock.exceptions.ConnectionError = requests.exceptions.ConnectionError
        requests_mock.post.side_effect = IOError()

        with self.assertRaises(IOError):
            telemetry.emit("metric_name", {})

    @patch("samcli.lib.telemetry.telemetry.DEFAULT_ENDPOINT_URL")
    def test_must_use_default_endpoint_url_if_not_customized(self, default_endpoint_url_mock):
        telemetry = Telemetry()

        self.assertEquals(telemetry._url, default_endpoint_url_mock)


def _ignore_other_attrs(data):

    common_attrs = ["requestId", "installationId", "sessionId", "executionEnvironment", "pyversion", "samcliVersion"]

    for a in common_attrs:
        if a not in data:
            data[a] = ANY

    return data
