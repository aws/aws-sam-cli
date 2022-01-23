import subprocess
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch, MagicMock, ANY, call
import os
from samcli.lib.utils.git_repo import GitRepo, rmtree_callback, CloneRepoException, CloneRepoUnstableStateException

REPO_URL = "REPO URL"
REPO_NAME = "REPO NAME"
CLONE_DIR = os.path.normpath("/tmp/local/clone/dir")
EXPECTED_DEFAULT_CLONE_PATH = os.path.normpath(os.path.join(CLONE_DIR, REPO_NAME))


class TestGitRepo(TestCase):
    def setUp(self):
        self.repo = GitRepo(url=REPO_URL)
        self.local_clone_dir = MagicMock()
        self.local_clone_dir.joinpath.side_effect = lambda sub_dir: os.path.normpath(os.path.join(CLONE_DIR, sub_dir))

    def test_ensure_clone_directory_exists(self):
        self.repo._ensure_clone_directory_exists(self.local_clone_dir)  # No exception is thrown
        self.local_clone_dir.mkdir.assert_called_once_with(mode=0o700, parents=True, exist_ok=True)

    def test_ensure_clone_directory_exists_fail(self):
        self.local_clone_dir.mkdir.side_effect = OSError
        with self.assertRaises(OSError):
            self.repo._ensure_clone_directory_exists(self.local_clone_dir)

    @patch("samcli.lib.utils.git_repo.subprocess.Popen")
    @patch("samcli.lib.utils.git_repo.platform.system")
    def test_git_executable_not_windows(self, mock_platform, mock_popen):
        mock_platform.return_value = "Not Windows"
        executable = self.repo._git_executable()
        self.assertEqual(executable, "git")

    @patch("samcli.lib.utils.git_repo.subprocess.Popen")
    @patch("samcli.lib.utils.git_repo.platform.system")
    def test_git_executable_windows(self, mock_platform, mock_popen):
        mock_platform.return_value = "Windows"
        executable = self.repo._git_executable()
        self.assertEqual(executable, "git")

    @patch("samcli.lib.utils.git_repo.subprocess.Popen")
    def test_git_executable_fails(self, mock_popen):
        mock_popen.side_effect = OSError("fail")
        with self.assertRaises(OSError):
            self.repo._git_executable()

    @patch("samcli.lib.utils.git_repo.Path.exists")
    @patch("samcli.lib.utils.git_repo.shutil")
    @patch("samcli.lib.utils.git_repo.check_output")
    @patch("samcli.lib.utils.git_repo.subprocess.Popen")
    @patch("samcli.lib.utils.git_repo.platform.system")
    def test_clone_happy_case(self, platform_mock, popen_mock, check_output_mock, shutil_mock, path_exist_mock):
        path_exist_mock.return_value = False
        self.repo.clone(clone_dir=self.local_clone_dir, clone_name=REPO_NAME)
        self.local_clone_dir.mkdir.assert_called_once_with(mode=0o700, parents=True, exist_ok=True)
        popen_mock.assert_called_once_with(["git"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        check_output_mock.assert_has_calls(
            [call(["git", "clone", self.repo.url, REPO_NAME], cwd=ANY, stderr=subprocess.STDOUT)]
        )
        shutil_mock.rmtree.assert_not_called()
        shutil_mock.copytree.assert_called_with(ANY, EXPECTED_DEFAULT_CLONE_PATH, ignore=ANY)
        shutil_mock.ignore_patterns.assert_called_with("*.git")

    @patch("samcli.lib.utils.git_repo.Path.exists")
    @patch("samcli.lib.utils.git_repo.shutil")
    @patch("samcli.lib.utils.git_repo.check_output")
    @patch("samcli.lib.utils.git_repo.subprocess.Popen")
    @patch("samcli.lib.utils.git_repo.platform.system")
    def test_clone_create_new_local_repo(
        self, platform_mock, popen_mock, check_output_mock, shutil_mock, path_exist_mock
    ):
        path_exist_mock.return_value = False
        self.repo.clone(clone_dir=self.local_clone_dir, clone_name=REPO_NAME)
        shutil_mock.rmtree.assert_not_called()
        shutil_mock.copytree.assert_called_with(ANY, EXPECTED_DEFAULT_CLONE_PATH, ignore=ANY)
        shutil_mock.ignore_patterns.assert_called_with("*.git")

    @patch("samcli.lib.utils.git_repo.Path.exists")
    @patch("samcli.lib.utils.git_repo.shutil")
    @patch("samcli.lib.utils.git_repo.check_output")
    @patch("samcli.lib.utils.git_repo.subprocess.Popen")
    @patch("samcli.lib.utils.git_repo.platform.system")
    def test_clone_replace_current_local_repo_if_replace_existing_flag_is_set(
        self, platform_mock, popen_mock, check_output_mock, shutil_mock, path_exist_mock
    ):
        path_exist_mock.return_value = True
        self.repo.clone(clone_dir=self.local_clone_dir, clone_name=REPO_NAME, replace_existing=True)
        self.local_clone_dir.mkdir.assert_called_once_with(mode=0o700, parents=True, exist_ok=True)
        shutil_mock.rmtree.assert_called_with(EXPECTED_DEFAULT_CLONE_PATH, onerror=rmtree_callback)
        shutil_mock.copytree.assert_called_with(ANY, EXPECTED_DEFAULT_CLONE_PATH, ignore=ANY)
        shutil_mock.ignore_patterns.assert_called_with("*.git")

    @patch("samcli.lib.utils.git_repo.Path.exists")
    @patch("samcli.lib.utils.git_repo.check_output")
    @patch("samcli.lib.utils.git_repo.subprocess.Popen")
    @patch("samcli.lib.utils.git_repo.platform.system")
    def test_clone_fail_if_current_local_repo_exists_and_replace_existing_flag_is_not_set(
        self, platform_mock, popen_mock, check_output_mock, path_exist_mock
    ):
        path_exist_mock.return_value = True
        with self.assertRaises(CloneRepoException):
            self.repo.clone(clone_dir=self.local_clone_dir, clone_name=REPO_NAME)  # replace_existing=False by default

    @patch("samcli.lib.utils.git_repo.shutil")
    @patch("samcli.lib.utils.git_repo.check_output")
    @patch("samcli.lib.utils.git_repo.subprocess.Popen")
    @patch("samcli.lib.utils.git_repo.platform.system")
    def test_clone_attempt_is_set_to_true_after_clone(self, platform_mock, popen_mock, check_output_mock, shutil_mock):
        self.assertFalse(self.repo.clone_attempted)
        self.repo.clone(clone_dir=self.local_clone_dir, clone_name=REPO_NAME)
        self.assertTrue(self.repo.clone_attempted)

    @patch("samcli.lib.utils.git_repo.shutil")
    @patch("samcli.lib.utils.git_repo.check_output")
    @patch("samcli.lib.utils.git_repo.subprocess.Popen")
    @patch("samcli.lib.utils.git_repo.platform.system")
    def test_clone_attempt_is_set_to_true_even_if_clone_failed(
        self, platform_mock, popen_mock, check_output_mock, shutil_mock
    ):
        check_output_mock.side_effect = subprocess.CalledProcessError("fail", "fail", "not found".encode("utf-8"))
        self.assertFalse(self.repo.clone_attempted)
        try:
            with self.assertRaises(CloneRepoException):
                self.repo.clone(clone_dir=self.local_clone_dir, clone_name=REPO_NAME)
        except:
            pass
        self.assertTrue(self.repo.clone_attempted)

    @patch("samcli.lib.utils.git_repo.shutil")
    @patch("samcli.lib.utils.git_repo.check_output")
    @patch("samcli.lib.utils.git_repo.subprocess.Popen")
    @patch("samcli.lib.utils.git_repo.platform.system")
    def test_clone_failed_to_create_the_clone_directory(
        self, platform_mock, popen_mock, check_output_mock, shutil_mock
    ):
        self.local_clone_dir.mkdir.side_effect = OSError
        try:
            with self.assertRaises(OSError):
                self.repo.clone(clone_dir=self.local_clone_dir, clone_name=REPO_NAME)
        except:
            pass
        self.local_clone_dir.mkdir.assert_called_once_with(mode=0o700, parents=True, exist_ok=True)
        popen_mock.assert_not_called()
        check_output_mock.assert_not_called()
        shutil_mock.assert_not_called()

    @patch("samcli.lib.utils.git_repo.shutil")
    @patch("samcli.lib.utils.git_repo.check_output")
    @patch("samcli.lib.utils.git_repo.subprocess.Popen")
    @patch("samcli.lib.utils.git_repo.platform.system")
    def test_clone_when_the_subprocess_fail(self, platform_mock, popen_mock, check_output_mock, shutil_mock):
        check_output_mock.side_effect = subprocess.CalledProcessError("fail", "fail", "any reason".encode("utf-8"))
        with self.assertRaises(CloneRepoException):
            self.repo.clone(clone_dir=self.local_clone_dir, clone_name=REPO_NAME)

    @patch("samcli.lib.utils.git_repo.LOG")
    @patch("samcli.lib.utils.git_repo.check_output")
    @patch("samcli.lib.utils.git_repo.subprocess.Popen")
    @patch("samcli.lib.utils.git_repo.platform.system")
    def test_clone_when_the_git_repo_not_found(self, platform_mock, popen_mock, check_output_mock, log_mock):
        check_output_mock.side_effect = subprocess.CalledProcessError("fail", "fail", "not found".encode("utf-8"))
        try:
            with self.assertRaises(CloneRepoException):
                self.repo.clone(clone_dir=self.local_clone_dir, clone_name=REPO_NAME)
        except Exception:
            pass
        log_mock.warning.assert_called()

    @patch("samcli.lib.utils.git_repo.Path.exists")
    @patch("samcli.lib.utils.git_repo.shutil")
    @patch("samcli.lib.utils.git_repo.check_output")
    @patch("samcli.lib.utils.git_repo.subprocess.Popen")
    @patch("samcli.lib.utils.git_repo.platform.system")
    def test_clone_when_failed_to_move_cloned_repo_from_temp_to_final_destination(
        self, platform_mock, popen_mock, check_output_mock, shutil_mock, path_exist_mock
    ):
        path_exist_mock.return_value = True
        shutil_mock.copytree.side_effect = OSError
        try:
            with self.assertRaises(CloneRepoUnstableStateException):
                self.repo.clone(clone_dir=self.local_clone_dir, clone_name=REPO_NAME, replace_existing=True)
        except Exception:
            pass
        shutil_mock.rmtree.assert_called_once_with(EXPECTED_DEFAULT_CLONE_PATH, onerror=rmtree_callback)
        shutil_mock.copytree.assert_called_once_with(ANY, EXPECTED_DEFAULT_CLONE_PATH, ignore=ANY)
        shutil_mock.ignore_patterns.assert_called_once_with("*.git")
