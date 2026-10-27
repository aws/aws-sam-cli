from unittest import TestCase
from unittest.mock import patch, Mock, MagicMock
from samcli.commands.exceptions import UserException
from samcli.lib.cookiecutter.template import Template
from samcli.lib.utils.template_hooks import UnsupportedTemplateHookError
from samcli.lib.cookiecutter.exceptions import (
    GenerateProjectFailedError,
    InvalidLocationError,
    PreprocessingError,
    PostprocessingError,
)
from cookiecutter.exceptions import RepositoryNotFound, UnknownRepoType


class TestTemplate(TestCase):
    _ANY_LOCATION = "any/path/to/cookiecutter/template"
    _INTERACTIVE_FLOW_MOCK = Mock()
    _PREPROCESSOR_MOCK = Mock()
    _POSTPROCESSOR_MOCK = Mock()
    _PLUGIN_MOCK = Mock()
    _ANY_INTERACTIVE_FLOW_CONTEXT = Mock()
    _ANY_PLUGIN_INTERACTIVE_FLOW_CONTEXT = Mock()
    _ANY_PROCESSOR_CONTEXT = Mock()

    @patch("samcli.lib.cookiecutter.interactive_flow")
    @patch("samcli.lib.cookiecutter.processor")
    @patch("samcli.lib.cookiecutter.processor")
    @patch("samcli.lib.cookiecutter.plugin")
    def test_creating_a_template(self, mock_plugin, mock_preprocessor, mock_postprocessor, mock_interactive_flow):
        # template with required attributes only should set defaults for others
        t = Template(location=self._ANY_LOCATION)
        self.assertEqual(t._location, self._ANY_LOCATION)
        self.assertEqual(t._interactive_flows, [])
        self.assertEqual(t._preprocessors, [])
        self.assertEqual(t._postprocessors, [])
        self.assertEqual(t._plugins, [])
        # template with all attributes
        t = Template(
            location=self._ANY_LOCATION,
            interactive_flows=[mock_interactive_flow],
            preprocessors=[mock_preprocessor],
            postprocessors=[mock_postprocessor],
            plugins=[mock_plugin],
        )
        self.assertEqual(t._location, self._ANY_LOCATION)
        self.assertEqual(t._interactive_flows[0], mock_interactive_flow)
        self.assertEqual(t._preprocessors[0], mock_preprocessor)
        self.assertEqual(t._postprocessors[0], mock_postprocessor)
        self.assertEqual(t._plugins[0], mock_plugin)
        t = Template(location=self._ANY_LOCATION, interactive_flows=[mock_interactive_flow])
        self.assertEqual(t._interactive_flows[0], mock_interactive_flow)
        t = Template(location=self._ANY_LOCATION, preprocessors=[mock_preprocessor])
        self.assertEqual(t._preprocessors[0], mock_preprocessor)
        t = Template(location=self._ANY_LOCATION, postprocessors=[mock_postprocessor])
        self.assertEqual(t._postprocessors[0], mock_postprocessor)
        t = Template(location=self._ANY_LOCATION, plugins=[mock_plugin])
        self.assertEqual(t._plugins[0], mock_plugin)
        # plugin's interactive flow and processors should be plugged into template's interactive flow and processors
        mock_plugin.interactive_flow = mock_interactive_flow
        mock_plugin.preprocessor = mock_preprocessor
        mock_plugin.postprocessor = mock_postprocessor
        t = Template(location=self._ANY_LOCATION, plugins=[mock_plugin])
        self.assertEqual(t._interactive_flows[0], mock_interactive_flow)
        self.assertEqual(t._preprocessors[0], mock_preprocessor)
        self.assertEqual(t._postprocessors[0], mock_postprocessor)
        self.assertEqual(t._plugins[0], mock_plugin)
        # template's location is required
        with self.assertRaises(TypeError):
            Template()

    @patch("samcli.lib.cookiecutter.interactive_flow")
    @patch("samcli.lib.cookiecutter.plugin")
    def test_run_interactive_flows(self, mock_plugin, mock_interactive_flow):
        # Template with no interactive-flows neither direct nor through a plugin
        t = Template(location=self._ANY_LOCATION)
        context = t.run_interactive_flows()
        self.assertEqual(context, {"shared_values": "default"})
        # Template with direct interactive flow only
        mock_interactive_flow.run.return_value = self._ANY_INTERACTIVE_FLOW_CONTEXT
        mock_plugin.interactive_flow = None
        t = Template(location=self._ANY_LOCATION, interactive_flows=[mock_interactive_flow], plugins=[mock_plugin])
        context = t.run_interactive_flows()
        mock_interactive_flow.run.assert_called_once()
        self.assertEqual(context, self._ANY_INTERACTIVE_FLOW_CONTEXT)
        # Template with direct interactive flow and a plugin's interactive flow
        mock_interactive_flow.reset_mock()
        mock_plugin.interactive_flow = MagicMock()
        mock_plugin.interactive_flow.run.return_value = self._ANY_PLUGIN_INTERACTIVE_FLOW_CONTEXT
        t = Template(location=self._ANY_LOCATION, interactive_flows=[mock_interactive_flow], plugins=[mock_plugin])
        context = t.run_interactive_flows()
        mock_interactive_flow.run.assert_called_once()
        mock_plugin.interactive_flow.run.assert_called_once()
        self.assertEqual(context, self._ANY_PLUGIN_INTERACTIVE_FLOW_CONTEXT)

    @patch("samcli.lib.cookiecutter.interactive_flow")
    @patch("samcli.lib.cookiecutter.plugin")
    def test_run_interactive_flows_throws_user_exception_if_something_wrong(self, mock_plugin, mock_interactive_flow):
        mock_interactive_flow.run.return_value = self._ANY_INTERACTIVE_FLOW_CONTEXT
        mock_plugin.interactive_flow.run.side_effect = Exception("something went wrong")
        t = Template(location=self._ANY_LOCATION, interactive_flows=[mock_interactive_flow], plugins=[mock_plugin])
        with self.assertRaises(UserException):
            t.run_interactive_flows()
            mock_interactive_flow.run.assert_called_once_with({})
            mock_plugin.interactive_flow.run.assert_called_once_with(self._ANY_INTERACTIVE_FLOW_CONTEXT)

    @patch("samcli.lib.cookiecutter.template.cookiecutter")
    def test_unsupported_hook_is_surfaced_as_a_user_error(self, mock_cookiecutter):
        # Otherwise the catch-all below turns an expected, actionable refusal into
        # GenerateProjectFailedError, which is not a UserException and so is reported to the user as
        # an unhandled exception with a "file a bug" link.
        mock_cookiecutter.side_effect = UnsupportedTemplateHookError("remove the hook")
        with self.assertRaises(UserException) as context:
            Template(location=self._ANY_LOCATION).generate_project(context={}, output_dir=Mock())
        self.assertEqual(str(context.exception), "remove the hook")
        self.assertEqual(context.exception.wrapped_from, "UnsupportedTemplateHookError")

    @patch("samcli.lib.cookiecutter.template.guarded_template_hooks")
    @patch("samcli.lib.cookiecutter.template.cookiecutter")
    def test_template_hooks_are_guarded_while_cookiecutter_runs(self, mock_cookiecutter, mock_guard):
        # The guard is a no-op unless running from a bundle, so without this every other test
        # would still pass if the wrapper were dropped.
        events = []
        mock_guard.return_value.__enter__.side_effect = lambda: events.append("enter")
        mock_guard.return_value.__exit__.side_effect = lambda *args: events.append("exit")
        mock_cookiecutter.side_effect = lambda **kwargs: events.append("cookiecutter")

        Template(location=self._ANY_LOCATION).generate_project(context={}, output_dir=Mock())

        self.assertEqual(events, ["enter", "cookiecutter", "exit"])

    @patch("samcli.lib.cookiecutter.template.cookiecutter")
    @patch("samcli.lib.cookiecutter.interactive_flow")
    @patch("samcli.lib.cookiecutter.processor")
    @patch("samcli.lib.cookiecutter.processor")
    def test_generate_project(self, mock_preprocessor, mock_postprocessor, mock_interactive_flow, mock_cookiecutter):
        t = Template(
            location=self._ANY_LOCATION,
            interactive_flows=[mock_interactive_flow],
            preprocessors=[mock_preprocessor],
            postprocessors=[mock_postprocessor],
        )
        mock_preprocessor.run.return_value = self._ANY_PROCESSOR_CONTEXT
        output_dir = Mock()
        t.generate_project(context=self._ANY_INTERACTIVE_FLOW_CONTEXT, output_dir=output_dir)
        mock_interactive_flow.run.assert_not_called()
        mock_preprocessor.run.assert_called_once_with(self._ANY_INTERACTIVE_FLOW_CONTEXT)
        mock_cookiecutter.assert_called_with(
            template=self._ANY_LOCATION,
            output_dir=output_dir,
            no_input=True,
            extra_context=self._ANY_PROCESSOR_CONTEXT,
            overwrite_if_exists=True,
        )
        mock_postprocessor.run.assert_called_once_with(self._ANY_PROCESSOR_CONTEXT)

    @patch("samcli.lib.cookiecutter.processor")
    def test_generate_project_preprocessors_exceptions(self, mock_preprocessor):
        t = Template(location=self._ANY_LOCATION, preprocessors=[mock_preprocessor])
        with self.assertRaises(PreprocessingError):
            mock_preprocessor.run.side_effect = Exception("something went wrong")
            t.generate_project({}, Mock())

    @patch("samcli.lib.cookiecutter.template.cookiecutter")
    @patch("samcli.lib.cookiecutter.processor")
    def test_generate_project_postprocessors_exceptions(self, mock_postprocessor, mock_cookiecutter):
        t = Template(location=self._ANY_LOCATION, postprocessors=[mock_postprocessor])
        with self.assertRaises(PostprocessingError):
            mock_postprocessor.run.side_effect = Exception("something went wrong")
            t.generate_project({}, Mock())

    @patch("samcli.lib.cookiecutter.template.generate_non_cookiecutter_project")
    @patch("samcli.lib.cookiecutter.template.cookiecutter")
    def test_generate_project_cookiecutter_exceptions(self, mock_cookiecutter, mock_generate_non_cookiecutter_project):
        t = Template(location=self._ANY_LOCATION)
        with self.assertRaises(InvalidLocationError):
            mock_cookiecutter.side_effect = UnknownRepoType()
            t.generate_project({}, Mock())
        mock_cookiecutter.reset_mock()
        with self.assertRaises(GenerateProjectFailedError):
            mock_cookiecutter.side_effect = Exception("something went wrong")
            t.generate_project({}, Mock())
        mock_cookiecutter.reset_mock()
        # if the provided template is not a cookiecutter template, we generate a non cookiecutter template
        mock_cookiecutter.side_effect = RepositoryNotFound()
        t.generate_project({}, Mock())
        mock_generate_non_cookiecutter_project.assert_called_once()
