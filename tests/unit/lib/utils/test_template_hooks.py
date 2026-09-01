import json
import logging
import tempfile
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from cookiecutter import hooks
from cookiecutter import main as cookiecutter_main
from cookiecutter.main import cookiecutter
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
        self.assertIn("remove the hook from the template", message)

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

    def test_only_our_own_refusal_traceback_is_dropped(self, patched_bundle):
        # cookiecutter logs the failure with logger.exception before re-raising, which would put a
        # traceback ahead of the remedy. Everything else it logs has to survive, so that a failing
        # shell hook still names the hook and --debug keeps its hook diagnostics.
        hooks_logger = logging.getLogger(hooks.__name__)
        with guarded_template_hooks():
            self.assertEqual(len(hooks_logger.filters), 1)
            log_filter = hooks_logger.filters[0]

            def record(exception):
                return logging.LogRecord(
                    hooks.__name__,
                    logging.ERROR,
                    __file__,
                    1,
                    "boom",
                    None,
                    (type(exception), exception, None) if exception else None,
                )

            self.assertFalse(log_filter.filter(record(UnsupportedTemplateHookError("refused"))))
            self.assertTrue(log_filter.filter(record(FailedHookException("shell hook failed"))))
            self.assertTrue(log_filter.filter(record(None)))
        self.assertEqual(hooks_logger.filters, [])

    def test_shell_hooks_are_delegated_untouched(self, patched_bundle):
        with patch.object(hooks, "run_script") as patched_original:
            with guarded_template_hooks():
                hooks.run_script("/tpl/hooks/post_gen_project.sh", "/project")
            patched_original.assert_called_once_with("/tpl/hooks/post_gen_project.sh", "/project")


class TestRealCookiecutterDispatch(TestCase):
    """Drives cookiecutter() itself, so a change in how it dispatches hooks cannot slip past.

    The tests above call the patched attributes directly, which would keep passing if cookiecutter
    started reaching its hook runners some other way -- and the guard would silently stop firing.
    """

    @staticmethod
    def _write_template(directory, hook_name=None):
        template = Path(directory, "tpl")
        (template / "{{cookiecutter.project_name}}").mkdir(parents=True)
        (template / "cookiecutter.json").write_text(json.dumps({"project_name": "app"}))
        (template / "{{cookiecutter.project_name}}" / "template.yaml").write_text("Resources: {}\n")
        if hook_name:
            (template / "hooks").mkdir()
            (template / "hooks" / hook_name).write_text("pass\n")
        output = Path(directory, "out")
        output.mkdir()
        return str(template), str(output)

    def test_every_python_hook_is_reached_through_cookiecutter(self):
        # pre_prompt is dispatched through cookiecutter.main, the other two through cookiecutter.hooks.
        for hook_name in ("pre_prompt.py", "pre_gen_project.py", "post_gen_project.py"):
            with self.subTest(hook=hook_name):
                with tempfile.TemporaryDirectory() as directory:
                    template, output = self._write_template(directory, hook_name)
                    with patch("samcli.lib.utils.template_hooks.is_pyinstaller_bundle", return_value=True):
                        with guarded_template_hooks():
                            with self.assertRaises(UnsupportedTemplateHookError):
                                cookiecutter(template=template, output_dir=output, no_input=True)

    def test_a_template_without_hooks_is_untouched(self):
        with tempfile.TemporaryDirectory() as directory:
            template, output = self._write_template(directory)
            with patch("samcli.lib.utils.template_hooks.is_pyinstaller_bundle", return_value=True):
                with guarded_template_hooks():
                    cookiecutter(template=template, output_dir=output, no_input=True)
            self.assertTrue(Path(output, "app", "template.yaml").is_file())
