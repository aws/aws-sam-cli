"""
test path_utils module
"""

from unittest import TestCase

from parameterized import parameterized

from samcli.lib.utils.path_utils import convert_path_to_unix_path, check_path_valid_type


class TestPathUtilities(TestCase):
    @parameterized.expand(
        [
            ("C:\\windows\\like\\path", "C:/windows/like/path"),
            ("/linux/path", "/linux/path"),
            ("..\\windows\\relative\\path", "../windows/relative/path"),
            ("..\\D:\\windows\\relative\\path", "../D:/windows/relative/path"),
            ("../linux/relative/path", "../linux/relative/path"),
        ]
    )
    def test_convert_path_to_unix_path(self, input_path, expected_path):
        output_path = convert_path_to_unix_path(input_path)
        self.assertEqual(output_path, expected_path)

    @parameterized.expand(
        [
            ("C:\\windows\\like\\path", True),
            ("test", True),
            (123456, True),
            ({"test": "test"}, False),
            ([1, 2, 3], False),
        ]
    )
    def test_check_valid_path(self, input_path, expected):
        self.assertEqual(check_path_valid_type(input_path), expected)
