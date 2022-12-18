import platform
import time

from parameterized import parameterized

import samcli

from unittest import TestCase
from unittest.mock import patch, Mock, ANY, call

import pytest

from samcli.lib.hook.exceptions import InvalidHookPackageConfigException
from samcli.lib.hook.hook_config import HookPackageConfig
from samcli.lib.iac.plugins_interfaces import ProjectTypes
from samcli.lib.telemetry.event import EventTracker

import samcli.lib.telemetry.metric
from samcli.lib.telemetry.cicd import CICDPlatform
from samcli.lib.telemetry.metric import (
    capture_return_value,
    _get_metric,
    send_installed_metric,
    track_command,
    track_template_warnings,
    capture_parameter,
    Metric,
    _get_project_details,
    ProjectDetails,
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
        assert metric.get_metric_name() == "installed"
        self.assertGreaterEqual(
            metric.get_data().items(), {"osPlatform": platform.system(), "telemetryEnabled": False}.items()
        )


class TestTrackWarning(TestCase):
    def setUp(self):
        TelemetryClassMock = Mock()
        GlobalConfigClassMock = Mock()
        self.telemetry_instance = TelemetryClassMock.return_value = Mock()
        self.gc_instance_mock = GlobalConfigClassMock.return_value = Mock()

        self.telemetry_class_patcher = patch("samcli.lib.telemetry.metric.Telemetry", TelemetryClassMock)
        self.gc_patcher = patch("samcli.lib.telemetry.metric.GlobalConfig", GlobalConfigClassMock)
        self.telemetry_class_patcher.start()
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
        self.telemetry_class_patcher.stop()
        self.gc_patcher.stop()

    @patch("samcli.lib.telemetry.metric.Context")
    @patch("samcli.lib.telemetry.metric.TemplateWarningsChecker")
    @patch("click.secho")
    def test_must_emit_true_warning_metric(self, secho_mock, TemplateWarningsCheckerMock, ContextMock):
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
        args, _ = self.telemetry_instance.emit.call_args_list[0]
        metric = args[0]
        assert metric.get_metric_name() == "templateWarning"
        self.assertGreaterEqual(metric.get_data().items(), expected_attrs.items())
        secho_mock.assert_called_with("WARNING: DummyWarningMessage", fg="yellow")

    @patch("samcli.lib.telemetry.metric.Context")
    @patch("samcli.lib.telemetry.metric.TemplateWarningsChecker")
    @patch("click.secho")
    def test_must_emit_false_warning_metric(self, secho_mock, TemplateWarningsCheckerMock, ContextMock):
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
        args, _ = self.telemetry_instance.emit.call_args_list[0]
        metric = args[0]
        assert metric.get_metric_name() == "templateWarning"
        self.assertGreaterEqual(metric.get_data().items(), expected_attrs.items())
        secho_mock.assert_not_called()


class TestTrackCommand(TestCase):
    def setUp(self):
        TelemetryClassMock = Mock()
        GlobalConfigClassMock = Mock()
        self.telemetry_instance = TelemetryClassMock.return_value = Mock()
        self.gc_instance_mock = GlobalConfigClassMock.return_value = Mock()
        EventTracker.clear_trackers()

        self.telemetry_class_patcher = patch("samcli.lib.telemetry.metric.Telemetry", TelemetryClassMock)
        self.gc_patcher = patch("samcli.lib.telemetry.metric.GlobalConfig", GlobalConfigClassMock)
        self.telemetry_class_patcher.start()
        self.gc_patcher.start()

        self.context_mock = Mock()
        self.context_mock.profile = False
        self.context_mock.debug = False
        self.context_mock.region = "myregion"
        self.context_mock.command_path = "fakesam local invoke"
        self.context_mock.experimental = False
        self.context_mock.template_dict = {}

        # Enable telemetry so we can actually run the tests
        self.gc_instance_mock.telemetry_enabled = True

    def tearDown(self):
        self.telemetry_class_patcher.stop()
        self.gc_patcher.stop()

    @patch("samcli.lib.telemetry.metric.Context")
    def test_must_emit_one_metric(self, ContextMock):
        ContextMock.get_current_context.return_value = self.context_mock

        def real_fn():
            pass

        track_command(real_fn)()

        args, _ = self.telemetry_instance.emit.call_args_list[0]
        metric = args[0]
        assert metric.get_metric_name() == "commandRun"
        self.assertEqual(self.telemetry_instance.emit.mock_calls, [call(ANY)], "The one command metric must be sent")

    @patch("samcli.lib.telemetry.metric.Context")
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
            "metricSpecificAttributes": ANY,
            "duration": ANY,
            "exitReason": "success",
            "exitCode": 0,
        }
        args, _ = self.telemetry_instance.emit.call_args_list[0]
        metric = args[0]
        assert metric.get_metric_name() == "commandRun"
        self.assertGreaterEqual(metric.get_data().items(), expected_attrs.items())

    @patch("samcli.lib.telemetry.metric.Context")
    def test_must_emit_command_run_metric_with_sanitized_profile_value(self, ContextMock):
        ContextMock.get_current_context.return_value = self.context_mock
        self.context_mock.profile = "myprofilename"

        def real_fn():
            pass

        track_command(real_fn)()

        expected_attrs = _ignore_common_attributes({"awsProfileProvided": True})
        args, _ = self.telemetry_instance.emit.call_args_list[0]
        metric = args[0]
        assert metric.get_metric_name() == "commandRun"
        self.assertGreaterEqual(metric.get_data().items(), expected_attrs.items())

    @pytest.mark.flaky(reruns=3)
    @patch("samcli.lib.telemetry.metric.Context")
    def test_must_record_function_duration(self, ContextMock):
        ContextMock.get_current_context.return_value = self.context_mock
        sleep_duration = 0.001  # 1 ms

        def real_fn():
            time.sleep(sleep_duration)

        track_command(real_fn)()

        # commandRun metric should be the only call to emit.
        # And grab the second argument passed to this call, which are the attributes
        args, _ = self.telemetry_instance.emit.call_args_list[0]
        metric = args[0]
        assert metric.get_metric_name() == "commandRun"
        self.assertGreaterEqual(
            metric.get_data()["duration"],
            sleep_duration,
            "Measured duration must be in milliseconds and greater than equal to the sleep duration",
        )

    @patch("samcli.lib.telemetry.metric.Context")
    def test_must_record_user_exception(self, ContextMock):
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
        args, _ = self.telemetry_instance.emit.call_args_list[0]
        metric = args[0]
        assert metric.get_metric_name() == "commandRun"
        self.assertGreaterEqual(metric.get_data().items(), expected_attrs.items())

    @patch("samcli.lib.telemetry.metric.Context")
    def test_must_record_wrapped_user_exception(self, ContextMock):
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
        args, _ = self.telemetry_instance.emit.call_args_list[0]
        metric = args[0]
        assert metric.get_metric_name() == "commandRun"
        self.assertGreaterEqual(metric.get_data().items(), expected_attrs.items())

    @patch("samcli.lib.telemetry.metric.Context")
    def test_must_record_any_exceptions(self, ContextMock):
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
        args, _ = self.telemetry_instance.emit.call_args_list[0]
        metric = args[0]
        assert metric.get_metric_name() == "commandRun"
        self.assertGreaterEqual(metric.get_data().items(), expected_attrs.items())

    @patch("samcli.lib.telemetry.metric.Context")
    def test_must_return_value_from_decorated_function(self, ContextMock):
        ContextMock.get_current_context.return_value = self.context_mock
        expected_value = "some return value"

        def real_fn():
            return expected_value

        actual = track_command(real_fn)()
        self.assertEqual(actual, "some return value")

    @patch("samcli.lib.telemetry.metric.get_hook_metadata", return_value=None)
    @patch("samcli.lib.telemetry.metric.Context")
    def test_must_pass_all_arguments_to_wrapped_function(self, ContextMock, get_hook_metadata_mock):
        def real_fn(*args, **kwargs):
            # simply return the arguments to be able to examine & assert
            return args, kwargs

        actual_args, actual_kwargs = track_command(real_fn)(1, 2, 3, a=1, b=2, c=3)
        self.assertEqual(actual_args, (1, 2, 3))
        self.assertEqual(actual_kwargs, {"a": 1, "b": 2, "c": 3})

    @patch("samcli.lib.telemetry.metric.Context")
    def test_must_decorate_functions(self, ContextMock):
        ContextMock.get_current_context.return_value = self.context_mock

        @track_command
        def real_fn(a, b=None):
            return "{} {}".format(a, b)

        actual = real_fn("hello", b="world")
        self.assertEqual(actual, "hello world")

        args, _ = self.telemetry_instance.emit.call_args_list[0]
        metric = args[0]
        assert metric.get_metric_name() == "commandRun"
        self.assertEqual(
            self.telemetry_instance.emit.mock_calls,
            [call(ANY)],
            "The command metrics be emitted when used as a decorator",
        )

    @patch("samcli.lib.telemetry.event.EventTracker.send_events", return_value=None)
    @patch("samcli.lib.telemetry.metric.Context")
    def test_must_send_events(self, ContextMock, send_mock):
        ContextMock.get_current_context.return_value = self.context_mock

        def real_fn():
            pass

        track_command(real_fn)()

        send_mock.assert_called()

    @patch("samcli.lib.telemetry.metric._get_project_details")
    @patch("samcli.lib.telemetry.event.EventTracker.send_events", return_value=None)
    @patch("samcli.lib.telemetry.metric.Context")
    def test_collects_project_details(self, ContextMock, send_mock, project_details_mock):
        ContextMock.get_current_context.return_value = self.context_mock
        project_details_mock.return_value = ProjectDetails(
            project_type="Terraform", hook_package_version="1.0.0", hook_name="terraform"
        )

        def real_fn(**kwargs):
            pass

        track_command(real_fn)(hook_name="terraform")
        args, _ = self.telemetry_instance.emit.call_args_list[0]
        metric_data = args[0]._data
        send_mock.assert_called()
        self.assertIn("metricSpecificAttributes", metric_data)
        metric_specific_attributes = metric_data.get("metricSpecificAttributes")
        self.assertEqual(metric_specific_attributes.get("projectType"), "Terraform")
        self.assertEqual(metric_specific_attributes.get("hookPackageId"), "terraform")
        self.assertEqual(metric_specific_attributes.get("hookPackageVersion"), "1.0.0")
        project_details_mock.assert_called_once_with("terraform", {})


class TestParameterCapture(TestCase):
    def setUp(self):
        self.mock_metrics = patch.object(samcli.lib.telemetry.metric, "_METRICS", {})

    def tearDown(self):
        pass

    def test_must_capture_positional_parameter(self):
        def test_func(arg1, arg2):
            return arg1, arg2

        with self.mock_metrics:
            assert len(samcli.lib.telemetry.metric._METRICS) == 0
            metric_name = "testMetric"
            arg1_data = "arg1 test data"
            arg2_data = "arg2 test data"
            capture_parameter(metric_name, "m1", 0)(test_func)(arg1_data, arg2_data)
            assert _get_metric(metric_name).get_data()["m1"] == arg1_data
            capture_parameter(metric_name, "m2", 1)(test_func)(arg1_data, arg2_data)
            assert _get_metric(metric_name).get_data()["m1"] == arg1_data
            assert _get_metric(metric_name).get_data()["m2"] == arg2_data

    def test_must_capture_positional_parameter_as_list(self):
        def test_func(arg1, arg2):
            return arg1, arg2

        with self.mock_metrics:
            assert len(samcli.lib.telemetry.metric._METRICS) == 0
            metric_name = "testMetric"
            arg1_data = "arg1 test data"
            arg2_data = "arg2 test data"
            capture_parameter(metric_name, "m1", 0, as_list=True)(test_func)(arg1_data, arg2_data)
            assert arg1_data in _get_metric(metric_name).get_data()["m1"]
            capture_parameter(metric_name, "m1", 1, as_list=True)(test_func)(arg1_data, arg2_data)
            assert arg1_data in _get_metric(metric_name).get_data()["m1"]
            assert arg2_data in _get_metric(metric_name).get_data()["m1"]

    def test_must_capture_named_parameter(self):
        def test_func(arg1, arg2, kwarg1=None, kwarg2=None):
            return arg1, arg2, kwarg1, kwarg2

        with self.mock_metrics:
            assert len(samcli.lib.telemetry.metric._METRICS) == 0
            metric_name = "testMetric"
            arg1_data = "arg1 test data"
            arg2_data = "arg2 test data"
            kwarg1_data = "kwarg1 test data"
            kwarg2_data = "kwarg2 test data"
            capture_parameter(metric_name, "km1", "kwarg1")(test_func)(
                arg1_data, arg2_data, kwarg1=kwarg1_data, kwarg2=kwarg2_data
            )
            assert _get_metric(metric_name).get_data()["km1"] == kwarg1_data
            capture_parameter(metric_name, "km2", "kwarg2")(test_func)(
                arg1_data, arg2_data, kwarg1=kwarg1_data, kwarg2=kwarg2_data
            )
            assert _get_metric(metric_name).get_data()["km1"] == kwarg1_data
            assert _get_metric(metric_name).get_data()["km2"] == kwarg2_data

    def test_must_capture_nested_parameter(self):
        def test_func(arg1, arg2):
            return arg1, arg2

        with self.mock_metrics:
            assert len(samcli.lib.telemetry.metric._METRICS) == 0
            metric_name = "testMetric"
            arg1_data = Mock()
            arg1_nested_data = "arg1 test data"
            arg1_data.nested_data = arg1_nested_data
            arg2_data = Mock()
            arg2_nested_data = "arg2 test data"
            arg2_data.nested.data = arg2_nested_data
            capture_parameter(metric_name, "m1", 0, parameter_nested_identifier="nested_data")(test_func)(
                arg1_data, arg2_data
            )
            assert _get_metric(metric_name).get_data()["m1"] == arg1_nested_data
            capture_parameter(metric_name, "m2", 1, parameter_nested_identifier="nested.data")(test_func)(
                arg1_data, arg2_data
            )
            assert _get_metric(metric_name).get_data()["m1"] == arg1_nested_data
            assert _get_metric(metric_name).get_data()["m2"] == arg2_nested_data

    def test_must_capture_return_value(self):
        def test_func(arg1, arg2):
            return arg1

        with self.mock_metrics:
            assert len(samcli.lib.telemetry.metric._METRICS) == 0
            metric_name = "testMetric"
            arg1_data = "arg1 test data"
            arg2_data = "arg2 test data"
            capture_return_value(metric_name, "m1")(test_func)(arg1_data, arg2_data)
            assert _get_metric(metric_name).get_data()["m1"] == arg1_data


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

        assert metric.get_data()["requestId"] == request_id
        assert metric.get_data()["installationId"] == installation_id
        assert metric.get_data()["sessionId"] == session_id
        assert metric.get_data()["executionEnvironment"] == execution_env
        assert metric.get_data()["ci"] == bool(ci)
        assert metric.get_data()["pyversion"] == python_version
        assert metric.get_data()["samcliVersion"] == samcli.__version__


def _ignore_common_attributes(data):
    common_attrs = ["requestId", "installationId", "sessionId", "executionEnvironment", "pyversion", "samcliVersion"]
    for a in common_attrs:
        if a not in data:
            data[a] = ANY

    return data


class TestGetProjectDetails(TestCase):
    @parameterized.expand(
        [
            (
                True,
                ProjectDetails(hook_name=None, hook_package_version=None, project_type=ProjectTypes.CDK.value),
            ),
            (
                False,
                ProjectDetails(hook_name=None, hook_package_version=None, project_type=ProjectTypes.CFN.value),
            ),
        ]
    )
    @patch("samcli.lib.telemetry.metric.is_cdk_project")
    def test_cfn_cdk_project_types(self, project_type_cdk, expected, cdk_project_mock):
        cdk_project_mock.return_value = project_type_cdk
        result = _get_project_details("", {})
        self.assertEqual(result, expected)

    @patch("samcli.lib.telemetry.metric.HookPackageConfig")
    @patch("samcli.lib.telemetry.metric.is_cdk_project")
    def test_terraform_project(self, cdk_project_mock, mock_hook_package_config):
        cdk_project_mock.return_value = False
        hook_package = Mock()
        hook_package.name = "terraform"
        hook_package.version = "1.0.0"
        hook_package.iac_framework = "Terraform"
        mock_hook_package_config.return_value = hook_package
        expected = ProjectDetails(hook_name="terraform", hook_package_version="1.0.0", project_type="Terraform")
        result = _get_project_details("terraform", {})
        self.assertEqual(result, expected)

    @patch("samcli.lib.telemetry.metric.HookPackageConfig")
    @patch("samcli.lib.telemetry.metric.get_hook_metadata")
    def test_terraform_project_from_metadata(self, get_hook_metadata_mock, mock_hook_package_config):
        get_hook_metadata_mock.return_value = {"HookName": "terraform"}
        hook_package = Mock()
        hook_package.name = "terraform"
        hook_package.version = "1.0.0"
        hook_package.iac_framework = "Terraform"
        mock_hook_package_config.return_value = hook_package
        expected = ProjectDetails(hook_name="terraform", hook_package_version="1.0.0", project_type="Terraform")
        result = _get_project_details("", {})
        self.assertEqual(result, expected)

    @patch("samcli.lib.telemetry.metric.HookPackageConfig")
    @patch("samcli.lib.telemetry.metric.is_cdk_project")
    def test_invalid_hook_id(self, cdk_project_mock, mock_hook_package_config):
        cdk_project_mock.return_value = False
        mock_hook_package_config.side_effect = InvalidHookPackageConfigException(message="Something went wrong")
        expected = ProjectDetails(hook_name="pulumi", hook_package_version=None, project_type="pulumi")
        result = _get_project_details("pulumi", {})
        self.assertEqual(result, expected)
