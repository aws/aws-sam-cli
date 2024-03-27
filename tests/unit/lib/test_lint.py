from unittest import TestCase
from unittest.mock import Mock, patch

from parameterized import parameterized

from samcli.lib.lint import get_lint_matches


class TestLint(TestCase):
    args_mock = Mock()
    filenames_mock = Mock()
    formatter_mock = Mock()
    get_args_filenames_mock = Mock()
    get_matches_mock = Mock()

    @parameterized.expand(
        [
            (("path/to/template", None, None), ["path/to/template"]),
            (("path/to/template", True, None), ["path/to/template", "--debug"]),
            (("path/to/template", False, "us-east-1"), ["path/to/template", "--region", "us-east-1"]),
        ]
    )
    @patch("cfnlint.core")
    def test_empty_matches(self, call_args, expect_called_args, cfnlint_mock):
        self.get_args_filenames_mock.return_value = (self.args_mock, self.filenames_mock, self.formatter_mock)
        cfnlint_mock.get_args_filenames = self.get_args_filenames_mock
        self.get_matches_mock.return_value = []
        cfnlint_mock.get_matches = self.get_matches_mock
        actual = get_lint_matches(*call_args)
        self.get_args_filenames_mock.assert_called_with(expect_called_args)
        self.get_matches_mock.assert_called_with(self.filenames_mock, self.args_mock)
        self.assertEqual(actual, ([], ""))

    @patch("cfnlint.core")
    def test_non_empty_matches(self, cfnlint_mock):
        self.get_args_filenames_mock.return_value = (self.args_mock, self.filenames_mock, self.formatter_mock)
        cfnlint_mock.get_args_filenames = self.get_args_filenames_mock
        match = Mock()
        self.get_matches_mock.return_value = [match]
        cfnlint_mock.get_matches = self.get_matches_mock
        cfnlint_mock.get_used_rules = Mock()
        self.formatter_mock.print_matches = Mock()
        self.formatter_mock.print_matches.return_value = "lint error"

        actual = get_lint_matches("path_to_template")
        self.get_args_filenames_mock.assert_called_with(["path_to_template"])
        self.get_matches_mock.assert_called_with(self.filenames_mock, self.args_mock)
        cfnlint_mock.get_used_rules.assert_called_once()
        self.formatter_mock.print_matches.assert_called_once()
        self.assertEqual(actual, ([match], "lint error"))
