import logging
from unittest import TestCase
from unittest.mock import patch

from cookiecutter import hooks
from cookiecutter import main as cookiecutter_main
from cookiecutter.exceptions import CookiecutterException, FailedHookException

from samcli.lib.utils.template_hooks import (
    UnsupportedTemplateHookError,
    guarded_template_hooks,
)


class TestGuardedTemplateHooksWhenNotBundled(TestCase):
    @patch("samcli.lib.utils.template_hooks.is_pyinstaller_bundle", return_value=False)
    def test_nothing_is_patched(self, patched_bundle):
        originals = (hooks.run_script, hooks.run_script_with_context, cookiecutter_main.run_pre_prompt_hook)
        with guarded_template_hooks():
            self.assertEqual(
                (hooks.run_script, hooks.run_script_with_context, cookiecutter_main.run_pre_prompt_hook),
                originals,
            )


@patch("samcli.lib.utils.template_hooks.is_pyinstaller_bundle", return_value=True)
class TestGuardedTemplateHooksWhenBundled(TestCase):
    def _originals(self):
        return hooks.run_script, hooks.run_script_with_context, cookiecutter_main.run_pre_prompt_hook

    def test_restores_everything_afterwards(self, patched_bundle):
        originals = self._originals()
        with guarded_template_hooks():
            self.assertNotEqual(self._originals(), originals)
        self.assertEqual(self._originals(), originals)

    def test_restores_everything_when_body_raises(self, patched_bundle):
        originals = self._originals()
        with self.assertRaises(ValueError):
            with guarded_template_hooks():
                raise ValueError("boom")
        self.assertEqual(self._originals(), originals)

    def test_rejects_python_hook_naming_it_and_the_remedy(self, patched_bundle):
        with guarded_template_hooks():
            with self.assertRaises(UnsupportedTemplateHookError) as context:
                hooks.run_script_with_context("/tpl/hooks/post_gen_project.py", "/project", {})
        message = str(context.exception)
        self.assertIn("post_gen_project.py", message)
        self.assertIn("re-install SAM CLI from pip", message)
        self.assertIn("remove the hook from the project", message)

    def test_run_script_is_a_backstop(self, patched_bundle):
        with guarded_template_hooks():
            with self.assertRaises(UnsupportedTemplateHookError):
                hooks.run_script("/tpl/hooks/pre_gen_project.py")

    def test_error_lets_cookiecutter_clean_up_the_project(self, patched_bundle):
        # Cookiecutter only removes the partially generated project for its own hook failure, and
        # samcli.lib.init only converts CookiecutterException into a user-facing error.
        self.assertTrue(issubclass(UnsupportedTemplateHookError, FailedHookException))
        self.assertTrue(issubclass(UnsupportedTemplateHookError, CookiecutterException))

    @patch("samcli.lib.utils.template_hooks.work_in")
    @patch("samcli.lib.utils.template_hooks.hooks.find_hook", return_value=["/tpl/hooks/pre_prompt.py"])
    def test_pre_prompt_hook_is_rejected_before_cookiecutter_runs_it(
        self, patched_find_hook, patched_work_in, patched_bundle
    ):
        # Checked up front because cookiecutter replaces a pre_prompt failure with its own message.
        original = cookiecutter_main.run_pre_prompt_hook
        with guarded_template_hooks():
            with self.assertRaises(UnsupportedTemplateHookError) as context:
                cookiecutter_main.run_pre_prompt_hook("/tpl")
        self.assertIn("pre_prompt.py", str(context.exception))
        self.assertEqual(cookiecutter_main.run_pre_prompt_hook, original)

    @patch("samcli.lib.utils.template_hooks.work_in")
    @patch("samcli.lib.utils.template_hooks.hooks.find_hook", return_value=[])
    def test_pre_prompt_delegates_when_there_is_no_python_hook(
        self, patched_find_hook, patched_work_in, patched_bundle
    ):
        with patch.object(cookiecutter_main, "run_pre_prompt_hook") as patched_original:
            patched_original.return_value = "/repo"
            with guarded_template_hooks():
                self.assertEqual(cookiecutter_main.run_pre_prompt_hook("/tpl"), "/repo")
            patched_original.assert_called_once_with("/tpl")

    def test_cookiecutter_hook_logging_is_quieted_and_restored(self, patched_bundle):
        # cookiecutter logs the failure with logger.exception before re-raising, which would put a
        # traceback ahead of the remedy. Filtered by level, since a logger with no handlers of its
        # own falls back to logging.lastResort and would still reach stderr.
        hooks_logger = logging.getLogger(hooks.__name__)
        original = hooks_logger.level
        with guarded_template_hooks():
            self.assertEqual(hooks_logger.level, logging.CRITICAL)
        self.assertEqual(hooks_logger.level, original)

    def test_shell_hooks_are_delegated_untouched(self, patched_bundle):
        with patch.object(hooks, "run_script") as patched_original:
            with guarded_template_hooks():
                hooks.run_script("/tpl/hooks/post_gen_project.sh", "/project")
            patched_original.assert_called_once_with("/tpl/hooks/post_gen_project.sh", "/project")
