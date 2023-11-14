from unittest import TestCase
from unittest.mock import Mock

from parameterized import parameterized

from samcli.lib.utils import lambda_builders


class TestPatchRuntime(TestCase):
    @parameterized.expand(
        [
            ("nodejs14.x", "nodejs14.x"),
            ("java8.al2", "java8"),
            ("dotnet6", "dotnet6"),
            ("provided", "provided"),
            ("provided.al2", "provided"),
            ("provided.al2023", "provided"),
        ]
    )
    def test_patch_runtime(self, runtime, expect):
        actual = lambda_builders.patch_runtime(runtime)
        self.assertEqual(actual, expect)
