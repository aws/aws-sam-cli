from unittest import TestCase
from unittest.mock import patch

from parameterized import parameterized_class


@parameterized_class(
    ("rie_env_var", "expected_log_level"),
    [
        (None, "error",),
        ("0", "error",),
        ("1", "debug"),
    ],
)
class TestRuntimeInterfaceEmulatorLogSettings(TestCase):
    rie_env_var = None
    expected_log_level = None

    def test_rie_debug_levels(self):
        with patch("samcli.local.docker.lambda_container.os.environ", {"SAM_CLI_RIE_DEV": self.rie_env_var}):
            from local.docker.lambda_container import  LambdaContainer
            self.assertEqual(LambdaContainer._RIE_LOG_LEVEL, self.expected_log_level)