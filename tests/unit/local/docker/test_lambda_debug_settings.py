from unittest import TestCase
from unittest.mock import patch

from parameterized import parameterized

from samcli.local.docker.lambda_debug_settings import LambdaDebugSettings


class TestLambdaDebugSettings(TestCase):
    @parameterized.expand(
        [
            (["-delveAPI=2"], 2),
            (["-delveAPI=1"], 1),
            (["-delveAPI", "2"], 2),
            (["-delveAPI", "1"], 1),
            # default should be 1
            ([], 1),
        ]
    )
    def test_delve_api_version_parsing(self, debug_arg_list, expected_api_version):
        self.assertEqual(LambdaDebugSettings.parse_go_delve_api_version(debug_arg_list), expected_api_version)

    @parameterized.expand(
        [
            (["-delveApi=2"],),
            (["-delveApi", "2"],),
        ]
    )
    def test_unrecognized_delve_api_version_parsing(self, debug_arg_list):
        with patch("samcli.local.docker.lambda_debug_settings.LOG.warning") as warning_mock:
            self.assertEqual(LambdaDebugSettings.parse_go_delve_api_version(debug_arg_list), 1)
            warning_mock.assert_called_once_with(
                'Ignoring unrecognized arguments: %s. Only "-delveAPI" is supported.', debug_arg_list
            )
