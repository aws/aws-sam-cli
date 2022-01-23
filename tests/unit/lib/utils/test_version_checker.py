from datetime import datetime, timedelta
from unittest import TestCase
from unittest.mock import patch, call, ANY

from samcli.cli.global_config import GlobalConfig
from samcli.lib.utils.version_checker import (
    check_newer_version,
    is_version_check_overdue,
    update_last_check_time,
    fetch_and_compare_versions,
    AWS_SAM_CLI_INSTALL_DOCS,
    AWS_SAM_CLI_PYPI_ENDPOINT,
    PYPI_CALL_TIMEOUT_IN_SECONDS,
)


@check_newer_version
def real_fn(a, b=None):
    return f"{a} {b}"


class TestVersionChecker(TestCase):
    def test_must_decorate_functions(self):
        actual = real_fn("Hello", "World")
        self.assertEqual(actual, "Hello World")

    @patch("samcli.lib.utils.version_checker.is_version_check_overdue")
    @patch("samcli.lib.utils.version_checker.fetch_and_compare_versions")
    @patch("samcli.lib.utils.version_checker.update_last_check_time")
    def test_must_call_fetch_and_compare_versions_if_newer_version_is_available(
        self, mock_update_last_check, mock_fetch_and_compare_versions, mock_is_version_check_overdue
    ):
        mock_is_version_check_overdue.return_value = True
        actual = real_fn("Hello", "World")

        self.assertEqual(actual, "Hello World")
        mock_is_version_check_overdue.assert_called_once()
        mock_fetch_and_compare_versions.assert_called_once()
        mock_update_last_check.assert_called_once()

    @patch("samcli.lib.utils.version_checker.is_version_check_overdue")
    @patch("samcli.lib.utils.version_checker.fetch_and_compare_versions")
    @patch("samcli.lib.utils.version_checker.update_last_check_time")
    def test_must_not_call_fetch_and_compare_versions_if_no_newer_version_is_available(
        self, mock_update_last_check, mock_fetch_and_compare_versions, mock_is_version_check_overdue
    ):
        mock_is_version_check_overdue.return_value = False
        actual = real_fn("Hello", "World")

        self.assertEqual(actual, "Hello World")
        mock_is_version_check_overdue.assert_called_once()

        mock_fetch_and_compare_versions.assert_not_called()
        mock_update_last_check.assert_not_called()

    @patch("samcli.lib.utils.version_checker.get")
    @patch("samcli.cli.global_config.GlobalConfig._get_value")
    def test_actual_function_should_return_on_exception(self, get_value_mock, get_mock):
        get_value_mock.return_value = None
        get_mock.side_effect = Exception()
        actual = real_fn("Hello", "World")
        self.assertEqual(actual, "Hello World")

    @patch("samcli.lib.utils.version_checker.get")
    @patch("samcli.lib.utils.version_checker.LOG")
    @patch("samcli.lib.utils.version_checker.installed_version", "1.9.0")
    def test_compare_invalid_response(self, mock_log, get_mock):
        get_mock.return_value.json.return_value = {}
        fetch_and_compare_versions()

        get_mock.assert_has_calls([call(AWS_SAM_CLI_PYPI_ENDPOINT, timeout=PYPI_CALL_TIMEOUT_IN_SECONDS)])

        mock_log.assert_has_calls(
            [
                call.debug("Installed version %s, current version %s", "1.9.0", None),
            ]
        )

    @patch("samcli.lib.utils.version_checker.get")
    @patch("samcli.lib.utils.version_checker.LOG")
    @patch("samcli.lib.utils.version_checker.installed_version", "1.9.0")
    def test_fetch_and_compare_versions_same(self, mock_log, get_mock):
        get_mock.return_value.json.return_value = {"info": {"version": "1.9.0"}}
        fetch_and_compare_versions()

        get_mock.assert_has_calls([call(AWS_SAM_CLI_PYPI_ENDPOINT, timeout=PYPI_CALL_TIMEOUT_IN_SECONDS)])

        mock_log.assert_has_calls(
            [
                call.debug("Installed version %s, current version %s", "1.9.0", "1.9.0"),
            ]
        )

    @patch("samcli.lib.utils.version_checker.get")
    @patch("samcli.lib.utils.version_checker.click")
    @patch("samcli.lib.utils.version_checker.installed_version", "1.9.0")
    def test_fetch_and_compare_versions_different(self, mock_click, get_mock):
        get_mock.return_value.json.return_value = {"info": {"version": "1.10.0"}}
        fetch_and_compare_versions()

        get_mock.assert_has_calls([call(AWS_SAM_CLI_PYPI_ENDPOINT, timeout=PYPI_CALL_TIMEOUT_IN_SECONDS)])

        mock_click.assert_has_calls(
            [
                call.secho("\nSAM CLI update available (1.10.0); (1.9.0 installed)", fg="green", err=True),
                call.echo(f"To download: {AWS_SAM_CLI_INSTALL_DOCS}", err=True),
            ]
        )

    @patch("samcli.lib.utils.version_checker.GlobalConfig")
    @patch("samcli.lib.utils.version_checker.datetime")
    def test_update_last_check_time(self, mock_datetime, mock_gc):
        mock_datetime.utcnow.return_value.timestamp.return_value = 12345
        update_last_check_time()
        self.assertEqual(mock_gc.return_value.last_version_check, 12345)

    @patch("samcli.cli.global_config.GlobalConfig.set_value")
    @patch("samcli.cli.global_config.GlobalConfig.get_value")
    def test_update_last_check_time_should_return_when_exception_is_raised(self, mock_gc_get_value, mock_gc_set_value):
        mock_gc_set_value.side_effect = Exception()
        update_last_check_time()

    def test_last_check_time_none_should_return_true(self):
        self.assertTrue(is_version_check_overdue(None))

    def test_last_check_time_week_older_should_return_true(self):
        eight_days_ago = datetime.utcnow() - timedelta(days=8)
        self.assertTrue(is_version_check_overdue(eight_days_ago))

    def test_last_check_time_week_earlier_should_return_false(self):
        six_days_ago = datetime.utcnow() - timedelta(days=6)
        self.assertFalse(is_version_check_overdue(six_days_ago.timestamp()))
