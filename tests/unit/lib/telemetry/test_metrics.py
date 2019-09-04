import platform
import time

from unittest import TestCase
from mock import patch, Mock, ANY, call

from samcli.lib.telemetry.metrics import send_installed_metric, track_command
from samcli.commands.exceptions import UserException


class TestSendInstalledMetric(TestCase):
    def setUp(self):
        self.gc_mock = Mock()
        self.global_config_patcher = patch("samcli.lib.telemetry.metrics.GlobalConfig", self.gc_mock)
        self.global_config_patcher.start()

    def tearDown(self):
        self.global_config_patcher.stop()

    @patch("samcli.lib.telemetry.metrics.Telemetry")
    def test_must_send_installed_metric_with_attributes(self, TelemetryClassMock):
        telemetry_mock = TelemetryClassMock.return_value = Mock()

        self.gc_mock.return_value.telemetry_enabled = False
        send_installed_metric()

        telemetry_mock.emit.assert_called_with(
            "installed", {"osPlatform": platform.system(), "telemetryEnabled": False}
        )


class TestTrackCommand(TestCase):
    def setUp(self):
        TelemetryClassMock = Mock()
        GlobalConfigClassMock = Mock()
        self.telemetry_instance = TelemetryClassMock.return_value = Mock()
        self.gc_instance_mock = GlobalConfigClassMock.return_value = Mock()

        self.telemetry_class_patcher = patch("samcli.lib.telemetry.metrics.Telemetry", TelemetryClassMock)
        self.gc_patcher = patch("samcli.lib.telemetry.metrics.GlobalConfig", GlobalConfigClassMock)
        self.telemetry_class_patcher.start()
        self.gc_patcher.start()

        self.context_mock = Mock()
        self.context_mock.profile = False
        self.context_mock.debug = False
        self.context_mock.region = "myregion"
        self.context_mock.command_path = "fakesam local invoke"

        # Enable telemetry so we can actually run the tests
        self.gc_instance_mock.telemetry_enabled = True

    def tearDown(self):
        self.telemetry_class_patcher.stop()
        self.gc_patcher.stop()

    @patch("samcli.lib.telemetry.metrics.Context")
    def test_must_emit_one_metric(self, ContextMock):
        ContextMock.get_current_context.return_value = self.context_mock

        def real_fn():
            pass

        track_command(real_fn)()

        self.assertEquals(
            self.telemetry_instance.emit.mock_calls, [call("commandRun", ANY)], "The one command metric must be sent"
        )

    @patch("samcli.lib.telemetry.metrics.Context")
    def test_must_emit_command_run_metric(self, ContextMock):
        ContextMock.get_current_context.return_value = self.context_mock

        def real_fn():
            pass

        track_command(real_fn)()

        expected_attrs = {
            "awsProfileProvided": False,
            "debugFlagProvided": False,
            "region": "myregion",
            "commandName": "fakesam local invoke",
            "duration": ANY,
            "exitReason": "success",
            "exitCode": 0,
        }
        self.telemetry_instance.emit.assert_has_calls([call("commandRun", expected_attrs)])

    @patch("samcli.lib.telemetry.metrics.Context")
    def test_must_emit_command_run_metric_with_sanitized_profile_value(self, ContextMock):
        ContextMock.get_current_context.return_value = self.context_mock
        self.context_mock.profile = "myprofilename"

        def real_fn():
            pass

        track_command(real_fn)()

        expected_attrs = _cmd_run_attrs({"awsProfileProvided": True})
        self.telemetry_instance.emit.assert_has_calls([call("commandRun", expected_attrs)])

    @patch("samcli.lib.telemetry.metrics.Context")
    def test_must_record_function_duration(self, ContextMock):
        ContextMock.get_current_context.return_value = self.context_mock
        sleep_duration = 0.01  # 10 millisecond

        def real_fn():
            time.sleep(sleep_duration)

        track_command(real_fn)()

        # commandRun metric should be the only call to emit.
        # And grab the second argument passed to this call, which are the attributes
        args, kwargs = self.telemetry_instance.emit.call_args_list[0]
        metric_name, actual_attrs = args
        self.assertEquals("commandRun", metric_name)
        self.assertGreaterEqual(
            actual_attrs["duration"],
            sleep_duration,
            "Measured duration must be in milliseconds and " "greater than equal to  the sleep duration",
        )

    @patch("samcli.lib.telemetry.metrics.Context")
    def test_must_record_user_exception(self, ContextMock):
        ContextMock.get_current_context.return_value = self.context_mock
        expected_exception = UserException("Something went wrong")
        expected_exception.exit_code = 1235

        def real_fn():
            raise expected_exception

        with self.assertRaises(UserException) as context:
            track_command(real_fn)()
            self.assertEquals(
                context.exception,
                expected_exception,
                "Must re-raise the original exception object " "without modification",
            )

        expected_attrs = _cmd_run_attrs({"exitReason": "UserException", "exitCode": 1235})
        self.telemetry_instance.emit.assert_has_calls([call("commandRun", expected_attrs)])

    @patch("samcli.lib.telemetry.metrics.Context")
    def test_must_record_any_exceptions(self, ContextMock):
        ContextMock.get_current_context.return_value = self.context_mock
        expected_exception = KeyError("IO Error test")

        def real_fn():
            raise expected_exception

        with self.assertRaises(KeyError) as context:
            track_command(real_fn)()
            self.assertEquals(
                context.exception,
                expected_exception,
                "Must re-raise the original exception object " "without modification",
            )

        expected_attrs = _cmd_run_attrs(
            {"exitReason": "KeyError", "exitCode": 255}  # Unhandled exceptions always use exit code 255
        )
        self.telemetry_instance.emit.assert_has_calls([call("commandRun", expected_attrs)])

    @patch("samcli.lib.telemetry.metrics.Context")
    def test_must_return_value_from_decorated_function(self, ContextMock):
        expected_value = "some return value"

        def real_fn():
            return expected_value

        actual = track_command(real_fn)()
        self.assertEquals(actual, "some return value")

    @patch("samcli.lib.telemetry.metrics.Context")
    def test_must_pass_all_arguments_to_wrapped_function(self, ContextMock):
        def real_fn(*args, **kwargs):
            # simply return the arguments to be able to examine & assert
            return args, kwargs

        actual_args, actual_kwargs = track_command(real_fn)(1, 2, 3, a=1, b=2, c=3)
        self.assertEquals(actual_args, (1, 2, 3))
        self.assertEquals(actual_kwargs, {"a": 1, "b": 2, "c": 3})

    @patch("samcli.lib.telemetry.metrics.Context")
    def test_must_decorate_functions(self, ContextMock):
        @track_command
        def real_fn(a, b=None):
            return "{} {}".format(a, b)

        actual = real_fn("hello", b="world")
        self.assertEquals(actual, "hello world")

        self.assertEquals(
            self.telemetry_instance.emit.mock_calls,
            [call("commandRun", ANY)],
            "The command metrics be emitted when used as a decorator",
        )

    def test_must_return_immediately_if_telemetry_is_disabled(self):
        def real_fn():
            return "hello"

        # Disable telemetry first
        self.gc_instance_mock.telemetry_enabled = False
        result = track_command(real_fn)()

        self.assertEquals(result, "hello")
        self.telemetry_instance.emit.assert_not_called()


def _cmd_run_attrs(data):
    common_attrs = [
        "awsProfileProvided",
        "debugFlagProvided",
        "region",
        "commandName",
        "duration",
        "exitReason",
        "exitCode",
    ]
    return _ignore_other_attrs(data, common_attrs)


def _ignore_other_attrs(data, common_attrs):
    for a in common_attrs:
        if a not in data:
            data[a] = ANY

    return data
