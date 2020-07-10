"""
Test arbitrary project init
"""

from unittest import TestCase
from unittest.mock import patch, ANY
from parameterized import parameterized

from pathlib import Path

from cookiecutter.exceptions import RepositoryNotFound
from samcli.lib.init.arbitrary_project import generate_non_cookiecutter_project, repository
from samcli.lib.init.exceptions import ArbitraryProjectDownloadFailed


class TestGenerateNonCookieCutterProject(TestCase):
    def setUp(self):
        self.output_dir = "output_dir"

    def tearDown(self):
        pass

    @parameterized.expand([("https://example.com/file.zip", True), ("/path/to/file.zip", False)])
    @patch("samcli.lib.init.arbitrary_project.osutils")
    def test_support_zip_files(self, location, is_url, osutils_mock):

        with patch.object(repository, "unzip") as unzip_mock:
            unzip_mock.return_value = "unzipped_dir"

            generate_non_cookiecutter_project(location, self.output_dir)

            unzip_mock.assert_called_with(zip_uri=location, is_url=is_url, no_input=True, clone_to_dir=ANY)

            osutils_mock.copytree.assert_called_with("unzipped_dir", self.output_dir, ignore=ANY)

    @patch("samcli.lib.init.arbitrary_project.osutils")
    def test_support_source_control_repos(self, osutils_mock):
        abbreviated_location = "gh:awslabs/aws-sam-cli"
        location = "https://github.com/awslabs/aws-sam-cli.git"

        with patch.object(repository, "clone") as clone_mock:
            clone_mock.return_value = "cloned_dir"

            generate_non_cookiecutter_project(abbreviated_location, self.output_dir)

            clone_mock.assert_called_with(repo_url=location, no_input=True, clone_to_dir=ANY)

            osutils_mock.copytree.assert_called_with("cloned_dir", self.output_dir, ignore=ANY)
            osutils_mock.mkdir_temp.assert_called_with(ignore_errors=True)

    def test_must_fail_on_local_folders(self):
        location = str(Path("my", "folder"))

        with self.assertRaises(ArbitraryProjectDownloadFailed):
            generate_non_cookiecutter_project(location, self.output_dir)

    def test_must_fail_when_repo_not_found(self):
        location = str(Path("my", "folder"))

        with patch.object(repository, "unzip") as unzip_mock:
            unzip_mock.side_effect = RepositoryNotFound("repo")

            with self.assertRaises(ArbitraryProjectDownloadFailed):
                generate_non_cookiecutter_project(location, self.output_dir)
