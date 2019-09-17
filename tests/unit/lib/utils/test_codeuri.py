import os
from unittest import TestCase
from parameterized import parameterized

from pathlib import Path

from samcli.lib.utils.codeuri import resolve_code_path


class TestLocalLambda_get_code_path(TestCase):
    def setUp(self):
        self.cwd = "/my/current/working/directory"
        self.relative_codeuri = "./my/path"
        self.absolute_codeuri = "/home/foo/bar"  # Some absolute path to use
        self.os_cwd = os.getcwd()

    @parameterized.expand([("."), ("")])
    def test_must_resolve_present_cwd(self, cwd_path):
        codeuri = self.relative_codeuri
        expected = os.path.normpath(os.path.join(self.os_cwd, codeuri))

        actual = resolve_code_path(cwd_path, codeuri)
        self.assertEqual(expected, actual)
        self.assertTrue(os.path.isabs(actual), "Result must be an absolute path")

    @parameterized.expand([("var/task"), ("some/dir")])
    def test_must_resolve_relative_cwd(self, cwd_path):

        codeuri = self.relative_codeuri

        abs_cwd = os.path.abspath(cwd_path)
        expected = os.path.normpath(os.path.join(abs_cwd, codeuri))

        actual = resolve_code_path(cwd_path, codeuri)
        self.assertEqual(expected, actual)
        self.assertTrue(os.path.isabs(actual), "Result must be an absolute path")

    @parameterized.expand([(""), ("."), ("hello"), ("a/b/c/d"), ("../../c/d/e")])
    def test_must_resolve_relative_codeuri(self, codeuri):

        expected = os.path.normpath(os.path.join(self.cwd, codeuri))

        actual = resolve_code_path(self.cwd, codeuri)
        self.assertEqual(str(Path(expected).resolve()), actual)
        self.assertTrue(os.path.isabs(actual), "Result must be an absolute path")

    @parameterized.expand([("/a/b/c"), ("/")])
    def test_must_resolve_absolute_codeuri(self, codeuri):

        expected = codeuri  # CodeUri must be return as is for absolute paths

        actual = resolve_code_path(None, codeuri)
        self.assertEqual(expected, actual)
        self.assertTrue(os.path.isabs(actual), "Result must be an absolute path")
