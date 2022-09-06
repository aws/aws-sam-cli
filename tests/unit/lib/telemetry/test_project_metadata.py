"""
Module for testing the project_metadata.py methods.
"""

import hashlib
from subprocess import CompletedProcess, CalledProcessError
from unittest.mock import patch, Mock
from unittest import TestCase

from parameterized import parameterized

from samcli.lib.telemetry.project_metadata import get_git_remote_origin_url, get_project_name, get_initial_commit_hash


class TestProjectMetadata(TestCase):
    def setUp(self):
        self.gc_mock = Mock()
        self.global_config_patcher = patch("samcli.lib.telemetry.project_metadata.GlobalConfig", self.gc_mock)
        self.global_config_patcher.start()
        self.gc_mock.return_value.telemetry_enabled = True

    def tearDown(self):
        self.global_config_patcher.stop()

    def test_return_none_when_telemetry_disabled(self):
        self.gc_mock.return_value.telemetry_enabled = False

        git_origin = get_git_remote_origin_url()
        self.assertIsNone(git_origin)

        project_name = get_project_name()
        self.assertIsNone(project_name)

        initial_commit = get_initial_commit_hash()
        self.assertIsNone(initial_commit)

    @parameterized.expand(
        [
            ("https://github.com/aws/aws-sam-cli.git\n", "github.com/aws/aws-sam-cli"),
            ("http://github.com/aws/aws-sam-cli.git/\n", "github.com/aws/aws-sam-cli"),
            ("http://example.com:8080/aws-sam-cli.git\n", "example.com/aws-sam-cli"),
            ("http://my_user@example.com/aws-sam-cli.git/\n", "example.com/aws-sam-cli"),
            ("git@github.com:aws/aws-sam-cli.git\n", "github.com/aws/aws-sam-cli"),
            ("https://github.com/aws/aws-cli.git\n", "github.com/aws/aws-cli"),
            ("http://not.a.real.site.com/somebody/my-project.git", "not.a.real.site.com/somebody/my-project"),
            ("git@not.github:person/my-project.git", "not.github/person/my-project"),
        ]
    )
    @patch("samcli.lib.telemetry.project_metadata.subprocess.run")
    def test_retrieve_git_origin(self, origin, expected, sp_mock):
        sp_mock.return_value = CompletedProcess(["git", "config", "--get", "remote.origin.url"], 0, stdout=origin)

        git_origin = get_git_remote_origin_url()
        expected_hash = hashlib.sha256()
        expected_hash.update(expected.encode("utf-8"))
        self.assertEqual(git_origin, expected_hash.hexdigest())

    @patch("samcli.lib.telemetry.project_metadata.subprocess.run")
    def test_retrieve_git_origin_when_not_a_repo(self, sp_mock):
        sp_mock.side_effect = CalledProcessError(128, ["git", "config", "--get", "remote.origin.url"])

        git_origin = get_git_remote_origin_url()
        self.assertIsNone(git_origin)

    @parameterized.expand(
        [
            ("https://github.com/aws/aws-sam-cli.git\n", "aws-sam-cli"),
            ("http://github.com/aws/aws-sam-cli.git\n", "aws-sam-cli"),
            ("http://example.com:8080/aws-sam-cli.git\n", "aws-sam-cli"),
            ("http://my_user@example.com/aws-sam-cli\n", "aws-sam-cli"),
            ("git@github.com:aws/aws-sam-cli.git\n", "aws-sam-cli"),
            ("https://github.com/aws/aws-cli/\n", "aws-cli"),
            ("http://not.a.real.site.com/somebody/my-project.git", "my-project"),
            ("git@not.github:person/my-project.git", "my-project"),
            ("user@example.com/some_project.git", "some_project"),
        ]
    )
    @patch("samcli.lib.telemetry.project_metadata.getcwd")
    @patch("samcli.lib.telemetry.project_metadata.subprocess.run")
    def test_retrieve_project_name_from_git(self, origin, expected, sp_mock, cwd_mock):
        sp_mock.return_value = CompletedProcess(["git", "config", "--get", "remote.origin.url"], 0, stdout=origin)
        cwd_mock.return_value = expected

        project_name = get_project_name()
        expected_hash = hashlib.sha256()
        expected_hash.update(expected.encode("utf-8"))
        self.assertEqual(project_name, expected_hash.hexdigest())

    @parameterized.expand(
        [
            ("C:/Users/aws/path/to/library/aws-sam-cli", "aws-sam-cli"),
            ("C:\\Users\\aws\\Windows\\path\\aws-sam-cli", "aws-sam-cli"),
            ("C:/", ""),
            ("C:\\", ""),
            ("E:/path/to/another/dir", "dir"),
            ("This/one/doesn't/start/with/a/letter", "letter"),
            ("/banana", "banana"),
            ("D:/one/more/just/to/be/safe", "safe"),
        ]
    )
    @patch("samcli.lib.telemetry.project_metadata.getcwd")
    @patch("samcli.lib.telemetry.project_metadata.subprocess.run")
    def test_retrieve_project_name_from_dir(self, cwd, expected, sp_mock, cwd_mock):
        sp_mock.side_effect = CalledProcessError(128, ["git", "config", "--get", "remote.origin.url"])
        cwd_mock.return_value = cwd

        project_name = get_project_name()
        expected_hash = hashlib.sha256()
        expected_hash.update(expected.encode("utf-8"))
        self.assertEqual(project_name, expected_hash.hexdigest())

    @parameterized.expand(
        [
            ("0000000000000000000000000000000000000000"),
            ("0123456789abcdef0123456789abcdef01234567"),
            ("abababababababababababababababababababab"),
        ]
    )
    @patch("samcli.lib.telemetry.project_metadata.subprocess.run")
    def test_retrieve_initial_commit(self, git_hash, sp_mock):
        sp_mock.return_value = CompletedProcess(["git", "rev-list", "--max-parents=0", "HEAD"], 0, stdout=git_hash)

        initial_commit = get_initial_commit_hash()
        expected_hash = hashlib.sha256()
        expected_hash.update(git_hash.encode("utf-8"))
        self.assertEqual(initial_commit, expected_hash.hexdigest())
