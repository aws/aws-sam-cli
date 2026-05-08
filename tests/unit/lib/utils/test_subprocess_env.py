"""
Tests for PyInstaller library path isolation in samcli.lib.utils.subprocess_utils module.
"""

import os
from unittest import TestCase
from unittest.mock import patch

from samcli.lib.utils.subprocess_utils import (
    LIBRARY_PATH_VARS,
    _filter_pyinstaller_paths,
    _library_path_state,
    get_clean_env_for_subprocess,
    get_original_library_paths,
    get_pyinstaller_lib_path,
    is_pyinstaller_bundle,
    isolate_library_paths_for_subprocess,
)


class TestIsPyinstallerBundle(TestCase):
    """Tests for is_pyinstaller_bundle function."""

    def test_returns_false_when_not_bundled(self):
        """Should return False when _MEIPASS is not set."""
        with patch("samcli.lib.utils.subprocess_utils.sys") as mock_sys:
            del mock_sys._MEIPASS
            mock_sys.configure_mock(**{"_MEIPASS": None})
            # hasattr will return False if we use spec
            mock_sys_no_meipass = type("MockSys", (), {})()
            with patch("samcli.lib.utils.subprocess_utils.sys", mock_sys_no_meipass):
                result = is_pyinstaller_bundle()
                self.assertFalse(result)

    def test_returns_true_when_bundled(self):
        """Should return True when _MEIPASS is set."""
        mock_sys = type("MockSys", (), {"_MEIPASS": "/tmp/pyinstaller_bundle"})()
        with patch("samcli.lib.utils.subprocess_utils.sys", mock_sys):
            result = is_pyinstaller_bundle()
            self.assertTrue(result)


class TestGetPyinstallerLibPath(TestCase):
    """Tests for get_pyinstaller_lib_path function."""

    def test_returns_none_when_not_bundled(self):
        """Should return None when not running from PyInstaller bundle."""
        mock_sys = type("MockSys", (), {})()
        with patch("samcli.lib.utils.subprocess_utils.sys", mock_sys):
            result = get_pyinstaller_lib_path()
            self.assertIsNone(result)

    def test_returns_internal_path_when_bundled(self):
        """Should return _internal path when running from bundle."""
        mock_sys = type("MockSys", (), {"_MEIPASS": "/tmp/bundle"})()
        with patch("samcli.lib.utils.subprocess_utils.sys", mock_sys):
            result = get_pyinstaller_lib_path()
            self.assertEqual(result, os.path.join("/tmp/bundle", "_internal"))


class TestFilterPyinstallerPaths(TestCase):
    """Tests for _filter_pyinstaller_paths function."""

    def test_returns_unchanged_when_not_bundled(self):
        """Should return path unchanged when not in PyInstaller bundle."""
        mock_sys = type("MockSys", (), {})()
        with patch("samcli.lib.utils.subprocess_utils.sys", mock_sys):
            path_value = "/usr/lib:/usr/local/lib"
            result = _filter_pyinstaller_paths(path_value)
            self.assertEqual(result, path_value)

    def test_filters_meipass_paths(self):
        """Should filter out paths starting with _MEIPASS."""
        mock_sys = type("MockSys", (), {"_MEIPASS": "/tmp/bundle"})()
        with patch("samcli.lib.utils.subprocess_utils.sys", mock_sys):
            path_value = f"/tmp/bundle/lib{os.pathsep}/usr/lib{os.pathsep}/tmp/bundle/_internal"
            result = _filter_pyinstaller_paths(path_value)
            self.assertEqual(result, "/usr/lib")

    def test_filters_internal_paths_ending_with_internal(self):
        """Should filter out paths ending with /_internal."""
        mock_sys = type("MockSys", (), {"_MEIPASS": "/tmp/bundle"})()
        with patch("samcli.lib.utils.subprocess_utils.sys", mock_sys):
            path_value = f"/some/path/_internal{os.pathsep}/usr/lib"
            result = _filter_pyinstaller_paths(path_value)
            self.assertEqual(result, "/usr/lib")

    def test_preserves_internal_in_middle_of_path(self):
        """Should preserve paths that have _internal in the middle (not ending with it)."""
        mock_sys = type("MockSys", (), {"_MEIPASS": "/tmp/bundle"})()
        with patch("samcli.lib.utils.subprocess_utils.sys", mock_sys):
            path_value = f"/usr/lib/some_internal_lib{os.pathsep}/usr/lib"
            result = _filter_pyinstaller_paths(path_value)
            self.assertEqual(result, f"/usr/lib/some_internal_lib{os.pathsep}/usr/lib")

    def test_filters_dist_internal_paths(self):
        """Should filter out paths containing dist/_internal."""
        mock_sys = type("MockSys", (), {"_MEIPASS": "/tmp/bundle"})()
        with patch("samcli.lib.utils.subprocess_utils.sys", mock_sys):
            path_value = f"/usr/local/aws-sam-cli/dist/_internal{os.pathsep}/usr/lib"
            result = _filter_pyinstaller_paths(path_value)
            self.assertEqual(result, "/usr/lib")

    def test_returns_empty_when_all_filtered(self):
        """Should return empty string when all paths are filtered."""
        mock_sys = type("MockSys", (), {"_MEIPASS": "/tmp/bundle"})()
        with patch("samcli.lib.utils.subprocess_utils.sys", mock_sys):
            path_value = f"/tmp/bundle/lib{os.pathsep}/tmp/bundle/_internal"
            result = _filter_pyinstaller_paths(path_value)
            self.assertEqual(result, "")


class TestIsolateLibraryPathsForSubprocess(TestCase):
    """Tests for isolate_library_paths_for_subprocess function."""

    def setUp(self):
        """Reset state before each test."""
        _library_path_state["original_library_paths"] = None

    def test_does_nothing_when_not_bundled(self):
        """Should not modify environment when not running from bundle."""
        mock_sys = type("MockSys", (), {})()
        original_env = os.environ.copy()
        with patch("samcli.lib.utils.subprocess_utils.sys", mock_sys):
            isolate_library_paths_for_subprocess()
        # Environment should be unchanged
        for var in LIBRARY_PATH_VARS:
            self.assertEqual(os.environ.get(var), original_env.get(var))

    def test_filters_library_paths_when_bundled(self):
        """Should filter library paths when running from bundle."""
        mock_sys = type("MockSys", (), {"_MEIPASS": "/tmp/bundle"})()
        test_var = "LD_LIBRARY_PATH"
        original_value = f"/tmp/bundle/_internal{os.pathsep}/usr/lib"

        with patch("samcli.lib.utils.subprocess_utils.sys", mock_sys):
            with patch.dict(os.environ, {test_var: original_value}, clear=False):
                isolate_library_paths_for_subprocess()
                self.assertEqual(os.environ.get(test_var), "/usr/lib")

    def test_removes_var_when_all_paths_filtered(self):
        """Should remove env var when all paths are PyInstaller paths."""
        mock_sys = type("MockSys", (), {"_MEIPASS": "/tmp/bundle"})()
        test_var = "LD_LIBRARY_PATH"
        original_value = "/tmp/bundle/_internal"

        _library_path_state["original_library_paths"] = None

        with patch("samcli.lib.utils.subprocess_utils.sys", mock_sys):
            env_backup = os.environ.get(test_var)
            try:
                os.environ[test_var] = original_value
                isolate_library_paths_for_subprocess()
                self.assertNotIn(test_var, os.environ)
            finally:
                if env_backup:
                    os.environ[test_var] = env_backup
                elif test_var in os.environ:
                    del os.environ[test_var]

    def test_saves_original_paths(self):
        """Should save original paths before modification."""
        mock_sys = type("MockSys", (), {"_MEIPASS": "/tmp/bundle"})()
        test_var = "LD_LIBRARY_PATH"
        original_value = f"/tmp/bundle/_internal{os.pathsep}/usr/lib"

        _library_path_state["original_library_paths"] = None

        with patch("samcli.lib.utils.subprocess_utils.sys", mock_sys):
            env_backup = os.environ.get(test_var)
            try:
                os.environ[test_var] = original_value
                isolate_library_paths_for_subprocess()
                saved_paths = get_original_library_paths()
                self.assertEqual(saved_paths.get(test_var), original_value)
            finally:
                if env_backup:
                    os.environ[test_var] = env_backup
                elif test_var in os.environ:
                    del os.environ[test_var]


class TestGetCleanEnvForSubprocess(TestCase):
    """Tests for get_clean_env_for_subprocess function."""

    def test_returns_copy_of_environ(self):
        """Should return a copy of os.environ."""
        mock_sys = type("MockSys", (), {})()
        with patch("samcli.lib.utils.subprocess_utils.sys", mock_sys):
            env = get_clean_env_for_subprocess()
            self.assertIsInstance(env, dict)
            # Should be a copy, not the same object
            self.assertIsNot(env, os.environ)

    def test_filters_library_paths_when_bundled(self):
        """Should filter library paths when running from bundle."""
        mock_sys = type("MockSys", (), {"_MEIPASS": "/tmp/bundle"})()
        test_var = "LD_LIBRARY_PATH"
        original_value = f"/tmp/bundle/_internal{os.pathsep}/usr/lib"

        with patch("samcli.lib.utils.subprocess_utils.sys", mock_sys):
            with patch.dict(os.environ, {test_var: original_value}, clear=False):
                env = get_clean_env_for_subprocess()
                self.assertEqual(env.get(test_var), "/usr/lib")

    def test_removes_additional_vars(self):
        """Should remove additional specified variables."""
        mock_sys = type("MockSys", (), {})()
        test_var = "MY_CUSTOM_VAR"

        with patch("samcli.lib.utils.subprocess_utils.sys", mock_sys):
            with patch.dict(os.environ, {test_var: "some_value"}, clear=False):
                env = get_clean_env_for_subprocess(additional_vars_to_remove=[test_var])
                self.assertNotIn(test_var, env)

    def test_handles_missing_additional_vars(self):
        """Should not fail when additional vars to remove don't exist."""
        mock_sys = type("MockSys", (), {})()

        with patch("samcli.lib.utils.subprocess_utils.sys", mock_sys):
            # Should not raise
            env = get_clean_env_for_subprocess(additional_vars_to_remove=["NONEXISTENT_VAR"])
            self.assertIsInstance(env, dict)

    def test_removes_var_when_all_paths_filtered_in_env_copy(self):
        """Should remove env var from copy when all paths are PyInstaller paths."""
        mock_sys = type("MockSys", (), {"_MEIPASS": "/tmp/bundle"})()
        test_var = "LD_LIBRARY_PATH"
        original_value = "/tmp/bundle/_internal"

        with patch("samcli.lib.utils.subprocess_utils.sys", mock_sys):
            with patch.dict(os.environ, {test_var: original_value}, clear=False):
                env = get_clean_env_for_subprocess()
                self.assertNotIn(test_var, env)
                # Original env should still have the value
                self.assertIn(test_var, os.environ)


class TestGetOriginalLibraryPaths(TestCase):
    """Tests for get_original_library_paths function."""

    def test_returns_empty_dict_when_no_original(self):
        """Should return empty dict when no original paths saved."""
        _library_path_state["original_library_paths"] = None
        result = get_original_library_paths()
        self.assertEqual(result, {})

    def test_returns_copy_of_original_paths(self):
        """Should return a copy of original paths."""
        original = {"LD_LIBRARY_PATH": "/some/path"}
        _library_path_state["original_library_paths"] = original
        result = get_original_library_paths()
        self.assertEqual(result, original)
        # Should be a copy
        self.assertIsNot(result, original)
