import platform
import requests

from unittest.mock import patch, Mock, ANY
from unittest import TestCase

from samcli.lib.telemetry.telemetry import Telemetry
from samcli import __version__ as samcli_version


class TestTelemetry(TestCase):
    def setUp(self):
        self.test_session_id = "TestSessionId"
        self.test_installation_id = "TestInstallationId"
        self.url = "some_test_url"

        self.metric_mock = Mock()
        self.metric_mock.get_metric_name.return_value = "metric_name"
        self.metric_mock.get_data.return_value = {"a": "1", "b": "2"}

    def tearDown(self):
        pass

    @patch("samcli.lib.telemetry.telemetry.requests")
    def test_must_add_metric_with_attributes_to_registry(self, requests_mock):
        telemetry = Telemetry(url=self.url)

        metric_name = "mymetric"
        attrs = {"a": 1, "b": 2}

        metric_mock = Mock()
        metric_mock.get_metric_name.return_value = metric_name
        metric_mock.get_data.return_value = attrs

        telemetry.emit(metric_mock)

        expected = {"metrics": [{metric_name: {"a": 1, "b": 2}}]}
        requests_mock.post.assert_called_once_with(ANY, json=expected, timeout=ANY)

    @patch("samcli.lib.telemetry.telemetry.requests")
    def test_default_request_should_be_fire_and_forget(self, requests_mock):
        telemetry = Telemetry(url=self.url)

        telemetry.emit(self.metric_mock)
        requests_mock.post.assert_called_once_with(ANY, json=ANY, timeout=(2, 0.1))  # 100ms response timeout

    @patch("samcli.lib.telemetry.telemetry.requests")
    def test_request_must_wait_for_2_seconds_for_response(self, requests_mock):
        telemetry = Telemetry(url=self.url)

        telemetry._send(self.metric_mock, wait_for_response=True)
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

        telemetry.emit(self.metric_mock)

    @patch("samcli.lib.telemetry.telemetry.requests")
    def test_must_swallow_connection_error_exception(self, requests_mock):
        telemetry = Telemetry(url=self.url)

        requests_mock.exceptions.Timeout = requests.exceptions.Timeout
        requests_mock.exceptions.ConnectionError = requests.exceptions.ConnectionError
        requests_mock.post.side_effect = requests.exceptions.ConnectionError()

        telemetry.emit(self.metric_mock)

    @patch("samcli.lib.telemetry.telemetry.requests")
    def test_must_raise_on_other_requests_exception(self, requests_mock):
        telemetry = Telemetry(url=self.url)

        requests_mock.exceptions.Timeout = requests.exceptions.Timeout
        requests_mock.exceptions.ConnectionError = requests.exceptions.ConnectionError
        requests_mock.post.side_effect = IOError()

        with self.assertRaises(IOError):
            telemetry.emit(self.metric_mock)

    @patch("samcli.lib.telemetry.telemetry.DEFAULT_ENDPOINT_URL")
    def test_must_use_default_endpoint_url_if_not_customized(self, default_endpoint_url_mock):
        telemetry = Telemetry()

        self.assertEqual(telemetry._url, default_endpoint_url_mock)
