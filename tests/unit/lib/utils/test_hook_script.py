import inspect
import os
import sys
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock, patch

from cookiecutter import hooks as cookiecutter_hooks

from samcli.lib.utils.hook_script import (
    HOOK_SCRIPT_ENV_VAR,
    find_system_interpreter,
    patched_hook_runner,
    run_hook_script_if_requested,
)


def _hooks_module(recorder):
    """A stand-in for cookiecutter.hooks whose run_script records the interpreter it would use."""

    def run_script(script_path, cwd="."):
        recorder.append((sys.executable, os.environ.get(HOOK_SCRIPT_ENV_VAR)))

    return SimpleNamespace(run_script=run_script)


class TestPatchedHookRunner(TestCase):
    @patch("samcli.lib.utils.hook_script.is_pyinstaller_bundle", return_value=False)
    def test_not_patched_when_not_frozen(self, patched_bundle):
        module = _hooks_module([])
        original = module.run_script
        with patched_hook_runner(module):
            self.assertIs(module.run_script, original)

    @patch("samcli.lib.utils.hook_script.is_pyinstaller_bundle", return_value=True)
    def test_restores_run_script_afterwards(self, patched_bundle):
        module = _hooks_module([])
        original = module.run_script
        with patched_hook_runner(module):
            self.assertIsNot(module.run_script, original)
        self.assertIs(module.run_script, original)

    @patch("samcli.lib.utils.hook_script.is_pyinstaller_bundle", return_value=True)
    def test_restores_run_script_when_body_raises(self, patched_bundle):
        module = _hooks_module([])
        original = module.run_script
        with self.assertRaises(ValueError):
            with patched_hook_runner(module):
                raise ValueError("boom")
        self.assertIs(module.run_script, original)

    @patch("samcli.lib.utils.hook_script.find_system_interpreter", return_value="/usr/bin/python3")
    @patch("samcli.lib.utils.hook_script.is_pyinstaller_bundle", return_value=True)
    def test_system_interpreter_used_for_python_hook(self, patched_bundle, patched_find):
        calls = []
        module = _hooks_module(calls)
        original_executable = sys.executable
        with patched_hook_runner(module):
            module.run_script("post_gen_project.py")
        self.assertEqual(calls, [("/usr/bin/python3", None)])
        self.assertEqual(sys.executable, original_executable)

    @patch("samcli.lib.utils.hook_script.find_system_interpreter", return_value=None)
    @patch("samcli.lib.utils.hook_script.is_pyinstaller_bundle", return_value=True)
    def test_falls_back_to_relaunching_this_executable(self, patched_bundle, patched_find):
        calls = []
        module = _hooks_module(calls)
        with patched_hook_runner(module):
            module.run_script("post_gen_project.py")
        # The executable is left alone; the env var tells the re-launched bundle to run the script.
        self.assertEqual(calls, [(sys.executable, "1")])
        self.assertNotIn(HOOK_SCRIPT_ENV_VAR, os.environ)

    @patch("samcli.lib.utils.hook_script.find_system_interpreter")
    @patch("samcli.lib.utils.hook_script.is_pyinstaller_bundle", return_value=True)
    def test_non_python_hook_is_delegated_untouched(self, patched_bundle, patched_find):
        calls = []
        module = _hooks_module(calls)
        with patched_hook_runner(module):
            module.run_script("post_gen_project.sh")
        self.assertEqual(calls, [(sys.executable, None)])
        patched_find.assert_not_called()


class TestFindSystemInterpreter(TestCase):
    @patch("samcli.lib.utils.hook_script.shutil.which", return_value=None)
    def test_returns_none_when_nothing_on_path(self, patched_which):
        self.assertIsNone(find_system_interpreter())

    @patch("samcli.lib.utils.hook_script.subprocess.run")
    @patch("samcli.lib.utils.hook_script.shutil.which")
    def test_skips_candidate_that_is_this_executable(self, patched_which, patched_run):
        patched_which.return_value = sys.executable
        self.assertIsNone(find_system_interpreter())
        patched_run.assert_not_called()

    @patch("samcli.lib.utils.hook_script.subprocess.run", return_value=Mock(returncode=1))
    @patch("samcli.lib.utils.hook_script.shutil.which", return_value="/fake/python3")
    def test_skips_candidate_that_is_not_an_interpreter(self, patched_which, patched_run):
        self.assertIsNone(find_system_interpreter())

    @patch("samcli.lib.utils.hook_script.subprocess.run", return_value=Mock(returncode=0))
    @patch("samcli.lib.utils.hook_script.shutil.which", return_value="/fake/python3")
    def test_returns_usable_interpreter(self, patched_which, patched_run):
        self.assertEqual(find_system_interpreter(), "/fake/python3")

    @patch("samcli.lib.utils.hook_script.subprocess.run", side_effect=OSError("nope"))
    @patch("samcli.lib.utils.hook_script.shutil.which", return_value="/fake/python3")
    def test_skips_candidate_that_cannot_be_executed(self, patched_which, patched_run):
        self.assertIsNone(find_system_interpreter())


class TestRunHookScriptIfRequested(TestCase):
    @patch("samcli.lib.utils.hook_script.runpy.run_path")
    def test_no_op_without_env_var(self, patched_run_path):
        os.environ.pop(HOOK_SCRIPT_ENV_VAR, None)
        run_hook_script_if_requested()
        patched_run_path.assert_not_called()

    @patch("samcli.lib.utils.hook_script.runpy.run_path")
    def test_runs_script_and_exits(self, patched_run_path):
        with patch.dict(os.environ, {HOOK_SCRIPT_ENV_VAR: "1"}):
            with patch.object(sys, "argv", ["sam", "/tmp/hook.py"]):
                with self.assertRaises(SystemExit) as context:
                    run_hook_script_if_requested()
        self.assertEqual(context.exception.code, 0)
        patched_run_path.assert_called_once_with("/tmp/hook.py", run_name="__main__")

    @patch("samcli.lib.utils.hook_script.runpy.run_path")
    def test_env_var_removed_so_nested_sam_calls_get_the_cli(self, patched_run_path):
        with patch.dict(os.environ, {HOOK_SCRIPT_ENV_VAR: "1"}):
            with patch.object(sys, "argv", ["sam", "/tmp/hook.py"]):
                with self.assertRaises(SystemExit):
                    run_hook_script_if_requested()
            self.assertNotIn(HOOK_SCRIPT_ENV_VAR, os.environ)

    @patch("samcli.lib.utils.hook_script.runpy.run_path")
    def test_no_op_without_a_script_argument(self, patched_run_path):
        with patch.dict(os.environ, {HOOK_SCRIPT_ENV_VAR: "1"}):
            with patch.object(sys, "argv", ["sam"]):
                run_hook_script_if_requested()
        patched_run_path.assert_not_called()


class TestCookiecutterPatchTarget(TestCase):
    """Guards the seam: a cookiecutter bump inside the pin must not silently un-patch us."""

    def test_run_script_exists_with_expected_signature(self):
        self.assertTrue(callable(cookiecutter_hooks.run_script))
        parameters = list(inspect.signature(cookiecutter_hooks.run_script).parameters)
        self.assertEqual(parameters, ["script_path", "cwd"])

    def test_run_script_still_uses_sys_executable(self):
        # The whole fix rests on run_script reading sys.executable at call time.
        source = inspect.getsource(cookiecutter_hooks.run_script)
        self.assertIn("sys.executable", source)
