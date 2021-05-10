from collections import defaultdict
import pathlib
import platform
import time
import uuid

from parameterized import parameterized

import samcli

from unittest import TestCase
from unittest.mock import patch, Mock, ANY, call

import samcli.lib.telemetry.metric
from samcli.lib.telemetry.cicd import CICDPlatform
from samcli.lib.telemetry.metric import (
    _get_global_metric_sink,
    flush,
    send_installed_metric,
    track_command,
    track_metric,
    track_template_warnings,
    Metric,
    MetricName,
)
from samcli.commands.exceptions import UserException


class TestSendInstalledMetric(TestCase):
    def setUp(self):
        self.gc_mock = Mock()
        self.global_config_patcher = patch("samcli.lib.telemetry.metric.GlobalConfig", self.gc_mock)
        self.global_config_patcher.start()

    def tearDown(self):
        self.global_config_patcher.stop()

    @patch("samcli.lib.telemetry.metric.Telemetry")
    def test_must_send_installed_metric_with_attributes(self, TelemetryClassMock):
        telemetry_mock = TelemetryClassMock.return_value = Mock()

        self.gc_mock.return_value.telemetry_enabled = False
        send_installed_metric()
        args, _ = telemetry_mock.emit.call_args_list[0]
        metric = args[0]
        assert metric.name == "installed"
        self.assertGreaterEqual(
            metric.data.items(), {"osPlatform": platform.system(), "telemetryEnabled": False}.items()
        )


class TestTrackWarning(TestCase):
    def setUp(self):
        GlobalConfigClassMock = Mock()
        self.gc_instance_mock = GlobalConfigClassMock.return_value = Mock()

        self.gc_patcher = patch("samcli.lib.telemetry.metric.GlobalConfig", GlobalConfigClassMock)
        self.gc_patcher.start()

        self.context_mock = Mock()
        self.context_mock.profile = False
        self.context_mock.debug = False
        self.context_mock.region = "myregion"
        self.context_mock.command_path = "fakesam local invoke"
        self.context_mock.template_dict = {}

        # Enable telemetry so we can actually run the tests
        self.gc_instance_mock.telemetry_enabled = True

    def tearDown(self):
        self.gc_patcher.stop()

    @patch("samcli.lib.telemetry.metric.Context")
    @patch("samcli.lib.telemetry.metric.TemplateWarningsChecker")
    @patch("samcli.lib.telemetry.metric.track_metric")
    @patch("click.secho")
    def test_must_track_true_warning_metric(
        self, secho_mock, track_metric_mock, TemplateWarningsCheckerMock, ContextMock
    ):
        ContextMock.get_current_context.return_value = self.context_mock
        template_warnings_checker_mock = TemplateWarningsCheckerMock.return_value = Mock()
        template_warnings_checker_mock.check_template_for_warning.return_value = "DummyWarningMessage"

        def real_fn():
            return True, "Dummy warning message"

        track_template_warnings(["DummyWarningName"])(real_fn)()

        expected_attrs = {
            "awsProfileProvided": False,
            "debugFlagProvided": False,
            "region": "myregion",
            "warningName": "DummyWarningName",
            "warningCount": 1,
        }
        track_metric_mock.assert_called_once_with(MetricName.templateWarning, top_level_attrs=expected_attrs)
        secho_mock.assert_called_with("WARNING: DummyWarningMessage", fg="yellow")

    @patch("samcli.lib.telemetry.metric.Context")
    @patch("samcli.lib.telemetry.metric.TemplateWarningsChecker")
    @patch("samcli.lib.telemetry.metric.track_metric")
    @patch("click.secho")
    def test_must_emit_false_warning_metric(
        self, secho_mock, track_metric_mock, TemplateWarningsCheckerMock, ContextMock
    ):
        ContextMock.get_current_context.return_value = self.context_mock
        template_warnings_checker_mock = TemplateWarningsCheckerMock.return_value = Mock()
        template_warnings_checker_mock.check_template_for_warning.return_value = None

        def real_fn():
            return False, ""

        track_template_warnings(["DummyWarningName"])(real_fn)()

        expected_attrs = {
            "awsProfileProvided": False,
            "debugFlagProvided": False,
            "region": "myregion",
            "warningName": "DummyWarningName",
            "warningCount": 0,
        }
        track_metric_mock.assert_called_once_with(MetricName.templateWarning, top_level_attrs=expected_attrs)
        secho_mock.assert_not_called()

    @patch("samcli.lib.telemetry.metric.Context")
    @patch("samcli.lib.telemetry.metric.TemplateWarningsChecker")
    @patch("samcli.lib.telemetry.metric._get_global_metric_sink", return_value=defaultdict(list))
    def test_must_keep_in_metric_sink(self, _get_global_metric_sink_mock, TemplateWarningsCheckerMock, ContextMock):
        ContextMock.get_current_context.return_value = self.context_mock
        template_warnings_checker_mock = TemplateWarningsCheckerMock.return_value = Mock()
        template_warnings_checker_mock.check_template_for_warning.return_value = "DummyWarningMessage"

        def real_fn():
            return True, "Dummy warning message"

        track_template_warnings(["DummyWarningName"])(real_fn)()
        expected_attrs = {
            "awsProfileProvided": False,
            "debugFlagProvided": False,
            "region": "myregion",
            "warningName": "DummyWarningName",
            "warningCount": 1,
        }
        metric_sink = _get_global_metric_sink_mock()
        metric = metric_sink[MetricName.templateWarning][0]
        assert metric.name == "templateWarning"
        self.assertGreaterEqual(metric.data.items(), expected_attrs.items())


class TestTrackCommand(TestCase):
    def setUp(self):
        GlobalConfigClassMock = Mock()
        self.gc_instance_mock = GlobalConfigClassMock.return_value = Mock()

        self.gc_patcher = patch("samcli.lib.telemetry.metric.GlobalConfig", GlobalConfigClassMock)
        self.gc_patcher.start()

        self.context_mock = Mock()
        self.context_mock.profile = False
        self.context_mock.debug = False
        self.context_mock.region = "myregion"
        self.context_mock.command_path = "fakesam local invoke"

        # Enable telemetry so we can actually run the tests
        self.gc_instance_mock.telemetry_enabled = True

    def tearDown(self):
        self.gc_patcher.stop()

    @patch("samcli.lib.telemetry.metric.Context")
    @patch("samcli.lib.telemetry.metric.track_metric")
    def test_call_track_metric(self, track_metric_mock, ContextMock):
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
        track_metric_mock.assert_called_once_with(
            MetricName.commandRun, top_level_attrs=expected_attrs, overwrite_existing_top_level_attrs=True
        )

    @patch("samcli.lib.telemetry.metric.Context")
    @patch("samcli.lib.telemetry.metric._get_global_metric_sink", return_value=defaultdict(list))
    def test_must_emit_command_run_metric(self, _get_global_metric_sink_mock, ContextMock):
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
            # "exitCode": 0,
        }
        metric_sink = _get_global_metric_sink_mock()
        metric = metric_sink[MetricName.commandRun][0]
        assert metric.name == "commandRun"
        self.assertGreaterEqual(metric.data.items(), expected_attrs.items())

    @patch("samcli.lib.telemetry.metric.Context")
    @patch("samcli.lib.telemetry.metric._get_global_metric_sink", return_value=defaultdict(list))
    def test_must_emit_command_run_metric_with_sanitized_profile_value(self, _get_global_metric_sink_mock, ContextMock):
        ContextMock.get_current_context.return_value = self.context_mock
        self.context_mock.profile = "myprofilename"

        def real_fn():
            pass

        track_command(real_fn)()

        expected_attrs = _ignore_common_attributes({"awsProfileProvided": True})
        metric_sink = _get_global_metric_sink_mock()
        metric = metric_sink[MetricName.commandRun][0]

        self.assertGreaterEqual(metric.data.items(), expected_attrs.items())

    @patch("samcli.lib.telemetry.metric.Context")
    @patch("samcli.lib.telemetry.metric._get_global_metric_sink", return_value=defaultdict(list))
    def test_must_record_function_duration(self, _get_global_metric_sink_mock, ContextMock):
        ContextMock.get_current_context.return_value = self.context_mock
        sleep_duration = 0.01  # 10 millisecond

        def real_fn():
            time.sleep(sleep_duration)

        track_command(real_fn)()

        # commandRun metric should be the only call to emit.
        # And grab the second argument passed to this call, which are the attributes
        metric_sink = _get_global_metric_sink_mock()
        metric = metric_sink[MetricName.commandRun][0]
        self.assertGreaterEqual(
            metric.data["duration"],
            sleep_duration,
            "Measured duration must be in milliseconds and " "greater than equal to  the sleep duration",
        )

    @patch("samcli.lib.telemetry.metric.Context")
    @patch("samcli.lib.telemetry.metric._get_global_metric_sink", return_value=defaultdict(list))
    def test_must_record_user_exception(self, _get_global_metric_sink_mock, ContextMock):
        ContextMock.get_current_context.return_value = self.context_mock
        expected_exception = UserException("Something went wrong")
        expected_exception.exit_code = 1235

        def real_fn():
            raise expected_exception

        with self.assertRaises(UserException) as context:
            track_command(real_fn)()
            self.assertEqual(
                context.exception,
                expected_exception,
                "Must re-raise the original exception object " "without modification",
            )

        expected_attrs = _ignore_common_attributes({"exitReason": "UserException", "exitCode": 1235})
        metric_sink = _get_global_metric_sink_mock()
        metric = metric_sink[MetricName.commandRun][0]
        assert metric.name == "commandRun"
        self.assertGreaterEqual(metric.data.items(), expected_attrs.items())

    @patch("samcli.lib.telemetry.metric.Context")
    @patch("samcli.lib.telemetry.metric._get_global_metric_sink", return_value=defaultdict(list))
    def test_must_record_wrapped_user_exception(self, _get_global_metric_sink_mock, ContextMock):
        ContextMock.get_current_context.return_value = self.context_mock
        expected_exception = UserException("Something went wrong", wrapped_from="CustomException")
        expected_exception.exit_code = 1235

        def real_fn():
            raise expected_exception

        with self.assertRaises(UserException) as context:
            track_command(real_fn)()
            self.assertEqual(
                context.exception,
                expected_exception,
                "Must re-raise the original exception object " "without modification",
            )

        expected_attrs = _ignore_common_attributes({"exitReason": "CustomException", "exitCode": 1235})
        metric_sink = _get_global_metric_sink_mock()
        metric = metric_sink[MetricName.commandRun][0]
        assert metric.name == "commandRun"
        self.assertGreaterEqual(metric.data.items(), expected_attrs.items())

    @patch("samcli.lib.telemetry.metric.Context")
    @patch("samcli.lib.telemetry.metric._get_global_metric_sink", return_value=defaultdict(list))
    def test_must_record_any_exceptions(self, _get_global_metric_sink_mock, ContextMock):
        ContextMock.get_current_context.return_value = self.context_mock
        expected_exception = KeyError("IO Error test")

        def real_fn():
            raise expected_exception

        with self.assertRaises(KeyError) as context:
            track_command(real_fn)()
            self.assertEqual(
                context.exception,
                expected_exception,
                "Must re-raise the original exception object " "without modification",
            )

        expected_attrs = _ignore_common_attributes(
            {"exitReason": "KeyError", "exitCode": 255}  # Unhandled exceptions always use exit code 255
        )
        metric_sink = _get_global_metric_sink_mock()
        metric = metric_sink[MetricName.commandRun][0]
        assert metric.name == "commandRun"
        self.assertGreaterEqual(metric.data.items(), expected_attrs.items())

    @patch("samcli.lib.telemetry.metric.Context")
    def test_must_return_value_from_decorated_function(self, ContextMock):
        expected_value = "some return value"

        def real_fn():
            return expected_value

        actual = track_command(real_fn)()
        self.assertEqual(actual, "some return value")

    @patch("samcli.lib.telemetry.metric.Context")
    def test_must_pass_all_arguments_to_wrapped_function(self, ContextMock):
        def real_fn(*args, **kwargs):
            # simply return the arguments to be able to examine & assert
            return args, kwargs

        actual_args, actual_kwargs = track_command(real_fn)(1, 2, 3, a=1, b=2, c=3)
        self.assertEqual(actual_args, (1, 2, 3))
        self.assertEqual(actual_kwargs, {"a": 1, "b": 2, "c": 3})

    @patch("samcli.lib.telemetry.metric.Context")
    @patch("samcli.lib.telemetry.metric.track_metric")
    def test_must_decorate_functions(self, track_metric_mock, ContextMock):
        ContextMock.get_current_context.return_value = self.context_mock

        @track_command
        def real_fn(a, b=None):
            return "{} {}".format(a, b)

        actual = real_fn("hello", b="world")
        self.assertEqual(actual, "hello world")

        expected_attrs = {
            "awsProfileProvided": False,
            "debugFlagProvided": False,
            "region": "myregion",
            "commandName": "fakesam local invoke",
            "duration": ANY,
            "exitReason": "success",
            "exitCode": 0,
        }
        track_metric_mock.assert_called_once_with(
            MetricName.commandRun,
            top_level_attrs=expected_attrs,
            overwrite_existing_top_level_attrs=True,
        )


class TestMetric(TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass

    @parameterized.expand([(CICDPlatform.Appveyor, "Appveyor", "ci"), (None, "CLI", False)])
    @patch("samcli.lib.telemetry.metric.CICDDetector.platform")
    @patch("samcli.lib.telemetry.metric.platform")
    @patch("samcli.lib.telemetry.metric.Context")
    @patch("samcli.lib.telemetry.metric.GlobalConfig")
    @patch("samcli.lib.telemetry.metric.uuid")
    def test_must_add_common_attributes(
        self, cicd_platform, execution_env, ci, uuid_mock, gc_mock, context_mock, platform_mock, cicd_platform_mock
    ):
        request_id = uuid_mock.uuid4.return_value = "fake requestId"
        installation_id = gc_mock.return_value.installation_id = "fake installation id"
        session_id = context_mock.get_current_context.return_value.session_id = "fake installation id"
        python_version = platform_mock.python_version.return_value = "8.8.0"
        cicd_platform_mock.return_value = cicd_platform

        metric = Metric("metric_name")

        assert metric.data["requestId"] == request_id
        assert metric.data["installationId"] == installation_id
        assert metric.data["sessionId"] == session_id
        assert metric.data["executionEnvironment"] == execution_env
        assert metric.data["ci"] == bool(ci)
        assert metric.data["pyversion"] == python_version
        assert metric.data["samcliVersion"] == samcli.__version__
        assert metric.data["metricSpecificAttributes"] == {}

    def test_must_not_add_common_attributes(self):
        metric = Metric("metric_name", should_add_common_attributes=False)
        self.assertTrue("requestId" not in metric)
        self.assertTrue("installationId" not in metric)
        self.assertTrue("sessionId" not in metric)
        self.assertTrue("executionEnvironment" not in metric)
        self.assertTrue("ci" not in metric)
        self.assertTrue("pyversion" not in metric)
        self.assertTrue("samcliVersion" not in metric)
        self.assertTrue("metricSpecificAttributes" not in metric)

    def test_metric_as_mutable_mapping(self):
        metric = Metric("metric_name", should_add_common_attributes=False)
        metric["key1"] = "value1"
        metric["key2"] = "value2"
        self.assertEqual(metric["key1"], metric.data["key1"])
        self.assertTrue("key1" in metric)
        self.assertTrue("key2" in metric)
        self.assertEqual(len(metric), 2)
        del metric["key1"]
        self.assertFalse("key1" in metric)
        self.assertEqual(len(metric), 1)
        for k, v in metric.items():
            self.assertEqual(k, "key2")
            self.assertEqual(v, "value2")
        self.assertTrue(bool(metric))
        del metric["key2"]
        self.assertFalse(bool(metric))


class TestMetricName(TestCase):
    def test_str(self):
        self.assertEqual(str(MetricName.installed), "installed")
        self.assertEqual(str(MetricName.commandRun), "commandRun")
        self.assertEqual(str(MetricName.templateWarning), "templateWarning")
        self.assertEqual(str(MetricName.runtimeMetric), "runtimeMetric")


class TestGetGlobalMetricSink(TestCase):
    @patch("samcli.lib.telemetry.metric._METRICS", {MetricName.installed: []})
    def test_must_return_singleton(self):
        metric_sink = _get_global_metric_sink()
        self.assertEqual(metric_sink, {MetricName.installed: []})

    @patch("samcli.lib.telemetry.metric._METRICS", None)
    def test_must_return_singleton_if_not_initialized(self):
        metric_sink = _get_global_metric_sink()
        self.assertEqual(metric_sink, {})


class TestFlush(TestCase):
    def setUp(self):
        TelemetryClassMock = Mock()
        self.telemetry_instance = TelemetryClassMock.return_value = Mock()
        self.telemetry_class_patcher = patch("samcli.lib.telemetry.metric.Telemetry", TelemetryClassMock)
        self.telemetry_class_patcher.start()

    def tearDown(self):
        self.telemetry_class_patcher.stop()

    @patch("samcli.lib.telemetry.metric._get_global_metric_sink")
    def test_must_emit(self, _get_global_metric_sink_mock):
        metrics = {
            "A": [
                Metric("A"),
                Metric("A"),
                Metric("A"),
            ],
            "B": [Metric("B"), Metric("B")],
        }
        _get_global_metric_sink_mock.return_value = metrics
        self.telemetry_instance.emit = Mock()
        flush()
        self.assertEqual(self.telemetry_instance.emit.call_count, 5)
        self.assertEqual(metrics, {"A": [], "B": []})


class TestTrackMetric(TestCase):
    def setUp(self):
        self.metric_sink = defaultdict(list)
        self.get_global_metric_sink_patcher = patch(
            "samcli.lib.telemetry.metric._get_global_metric_sink", return_value=self.metric_sink
        )
        self.get_global_metric_sink_patcher.start()

    def tearDown(self):
        self.get_global_metric_sink_patcher.stop()

    def test_must_track_metric(self):
        metric_name = MetricName.installed
        track_metric(
            metric_name=metric_name,
        )
        self.assertEqual(len(self.metric_sink[metric_name]), 1)

    def test_report_more_than_once(self):
        metric_name = MetricName.templateWarning
        track_metric(metric_name)
        track_metric(metric_name)
        self.assertFalse(metric_name.can_report_once_only)
        self.assertEqual(len(self.metric_sink[metric_name]), 2)

    def test_report_only_once(self):
        metric_name = MetricName.commandRun
        track_metric(metric_name)
        track_metric(metric_name)
        self.assertTrue(metric_name.can_report_once_only)
        self.assertEqual(len(self.metric_sink[metric_name]), 1)

    def test_track_metric_with_metric_specific_attrs(self):
        metric_name = MetricName.commandRun
        metric_specific_attrs = {"key1": "value1", "key2": "value2"}
        track_metric(metric_name, metric_specific_attrs=metric_specific_attrs)
        metric = self.metric_sink[metric_name][0]
        self.assertEqual(metric["metricSpecificAttributes"], metric_specific_attrs)

    def test_overwrite_exisiting_metric_specific_attrs(self):
        metric_name = MetricName.commandRun
        metric_specific_attrs = {"key1": "value1", "key2": "value2"}
        track_metric(metric_name, metric_specific_attrs=metric_specific_attrs)
        track_metric(
            metric_name, metric_specific_attrs={"key2": "value1"}, overwrite_existing_metric_specific_attrs=True
        )
        metric = self.metric_sink[metric_name][0]
        self.assertEqual(metric["metricSpecificAttributes"], {"key1": "value1", "key2": "value1"})

    def test_not_overwrite_exisiting_metric_specific_attrs(self):
        metric_name = MetricName.commandRun
        metric_specific_attrs = {"key1": "value1", "key2": "value2"}
        track_metric(metric_name, metric_specific_attrs=metric_specific_attrs)
        track_metric(
            metric_name, metric_specific_attrs={"key2": "value1"}, overwrite_existing_metric_specific_attrs=False
        )
        metric = self.metric_sink[metric_name][0]
        self.assertEqual(metric["metricSpecificAttributes"], {"key1": "value1", "key2": "value2"})

    def test_track_metric_with_top_level_attrs(self):
        metric_name = MetricName.commandRun
        top_level_attrs = {"key1": "value1", "key2": "value2"}
        track_metric(metric_name, top_level_attrs=top_level_attrs)
        metric = self.metric_sink[metric_name][0]
        self.assertEqual(metric["key1"], "value1")
        self.assertEqual(metric["key2"], "value2")

    def test_overwrite_existing_top_level_attrs(self):
        metric_name = MetricName.commandRun
        track_metric(
            metric_name,
            top_level_attrs={
                "region": "myregion",
            },
        )
        track_metric(
            metric_name,
            top_level_attrs={
                "region": "yourregion",
            },
            overwrite_existing_top_level_attrs=True,
        )
        metric = self.metric_sink[metric_name][0]
        self.assertEqual(metric["region"], "yourregion")

    def test_not_overwrite_existing_top_level_attrs(self):
        metric_name = MetricName.commandRun
        track_metric(
            metric_name,
            top_level_attrs={
                "region": "myregion",
            },
        )
        track_metric(
            metric_name,
            top_level_attrs={
                "region": "yourregion",
            },
            overwrite_existing_top_level_attrs=False,
        )
        metric = self.metric_sink[metric_name][0]
        self.assertEqual(metric["region"], "myregion")


def _ignore_common_attributes(data):
    common_attrs = [
        "requestId",
        "installationId",
        "sessionId",
        "executionEnvironment",
        "pyversion",
        "samcliVersion",
        "metricSpecificAttributes",
    ]
    for a in common_attrs:
        if a not in data:
            data[a] = ANY

    return data
