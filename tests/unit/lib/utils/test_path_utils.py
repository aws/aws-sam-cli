"""
test path_utils module
"""

from unittest import TestCase, skipIf

from parameterized import parameterized

from samcli.lib.utils.path_utils import check_path_valid_type, convert_path_to_unix_path, is_same_or_ancestor
from tests.testing_utils import IS_WINDOWS


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

    @parameterized.expand(
        [
            ("/project", "/project", True),
            ("/workspace", "/workspace/project", True),
            ("/", "/workspace/project", True),
            ("/workspace/", "/workspace/project", True),
            ("/project/.aws-sam", "/project", False),
            ("/project/.aws-sam/build", "/project", False),
            ("/proj", "/project", False),
            ("/other", "/project", False),
        ]
    )
    @skipIf(IS_WINDOWS, "POSIX paths")
    def test_is_same_or_ancestor(self, ancestor, path, expected):
        self.assertEqual(is_same_or_ancestor(ancestor, path), expected)

    @parameterized.expand(
        [
            ("C:\\Workspace", "c:\\workspace\\project", True),
            ("C:\\workspace\\project\\.aws-sam", "C:\\workspace\\project", False),
            ("D:\\", "C:\\workspace\\project", False),
        ]
    )
    @skipIf(not IS_WINDOWS, "Windows paths")
    def test_is_same_or_ancestor_windows(self, ancestor, path, expected):
        self.assertEqual(is_same_or_ancestor(ancestor, path), expected)
