from unittest import TestCase
from unittest.mock import patch, Mock

from parameterized import parameterized

from samcli.local.docker.lambda_debug_settings import DebuggingNotSupported, LambdaDebugSettings, Runtime

_DEBUG_RUNTIMES = [
    Runtime.java8,
    Runtime.java8al2,
    Runtime.java11,
    Runtime.dotnetcore21,
    Runtime.dotnetcore31,
    Runtime.go1x,
    Runtime.nodejs10x,
    Runtime.nodejs12x,
    Runtime.nodejs14x,
    Runtime.python27,
    Runtime.python36,
    Runtime.python37,
    Runtime.python38,
]


class TestLambdaDebugSetting(TestCase):
    @parameterized.expand([(runtime,) for runtime in _DEBUG_RUNTIMES])
    @patch("samcli.local.docker.lambda_debug_settings.DebugSettings")
    def test_only_one_debug_setting_is_created(self, runtime, debug_settings_mock):
        LambdaDebugSettings.get_debug_settings(1234, [], {}, runtime.value, {})
        debug_settings_mock.assert_called_once()

    @parameterized.expand([(runtime,) for runtime in Runtime if runtime not in _DEBUG_RUNTIMES])
    @patch("samcli.local.docker.lambda_debug_settings.DebugSettings")
    def test_debugging_not_supported_raised(self, runtime, debug_settings_mock):
        with self.assertRaises(DebuggingNotSupported):
            LambdaDebugSettings.get_debug_settings(1234, [], {}, runtime.value, {})
        debug_settings_mock.assert_not_called()

    @parameterized.expand([(runtime,) for runtime in _DEBUG_RUNTIMES if runtime != Runtime.go1x])
    @patch("samcli.local.docker.lambda_debug_settings.LambdaDebugSettings.parse_go_delve_api_version")
    def test_parse_go_delve_api_version_not_called_for_other_runtimes(self, runtime, parse_go_delve_api_version_mock):
        LambdaDebugSettings.get_debug_settings(1234, [], {}, runtime.value, {})
        parse_go_delve_api_version_mock.assert_not_called()

    @patch("samcli.local.docker.lambda_debug_settings.LambdaDebugSettings.parse_go_delve_api_version")
    def test_parse_go_delve_api_version_called_for_go_runtimes(self, parse_go_delve_api_version_mock):
        debug_args_list = Mock()
        LambdaDebugSettings.get_debug_settings(1234, debug_args_list, {}, Runtime.go1x.value, {})
        parse_go_delve_api_version_mock.assert_called_once_with(debug_args_list)
