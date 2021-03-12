from unittest import TestCase
from unittest.mock import patch, Mock, MagicMock
from samcli.commands.exceptions import UserException
from samcli.lib.cookiecutter.template import Template
from samcli.lib.cookiecutter.exceptions import GenerateProjectFailedError, InvalidLocationError
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
        assert t._location == self._ANY_LOCATION
        assert t._interactive_flows == []
        assert t._preprocessors == []
        assert t._postprocessors == []
        assert t._plugins == []
        # template with all attributes
        t = Template(
            location=self._ANY_LOCATION,
            interactive_flows=[mock_interactive_flow],
            preprocessors=[mock_preprocessor],
            postprocessors=[mock_postprocessor],
            plugins=[mock_plugin],
        )
        assert t._location == self._ANY_LOCATION
        assert t._interactive_flows[0] == mock_interactive_flow
        assert t._preprocessors[0] == mock_preprocessor
        assert t._postprocessors[0] == mock_postprocessor
        assert t._plugins[0] == mock_plugin
        t = Template(location=self._ANY_LOCATION, interactive_flows=[mock_interactive_flow])
        assert t._interactive_flows[0] == mock_interactive_flow
        t = Template(location=self._ANY_LOCATION, preprocessors=[mock_preprocessor])
        assert t._preprocessors[0] == mock_preprocessor
        t = Template(location=self._ANY_LOCATION, postprocessors=[mock_postprocessor])
        assert t._postprocessors[0] == mock_postprocessor
        t = Template(location=self._ANY_LOCATION, plugins=[mock_plugin])
        assert t._plugins[0] == mock_plugin
        # plugin's interactive flow and processors should be plugged into template's interactive flow and processors
        mock_plugin.interactive_flow = mock_interactive_flow
        mock_plugin.preprocessor = mock_preprocessor
        mock_plugin.postprocessor = mock_postprocessor
        t = Template(location=self._ANY_LOCATION, plugins=[mock_plugin])
        assert t._interactive_flows[0] == mock_interactive_flow
        assert t._preprocessors[0] == mock_preprocessor
        assert t._postprocessors[0] == mock_postprocessor
        assert t._plugins[0] == mock_plugin
        # template's location is required
        with self.assertRaises(TypeError):
            Template()

    @patch("samcli.lib.cookiecutter.interactive_flow")
    @patch("samcli.lib.cookiecutter.plugin")
    def test_run_interactive_flows(self, mock_plugin, mock_interactive_flow):
        # Template with no interactive-flows neither direct nor through a plugin
        t = Template(location=self._ANY_LOCATION)
        context = t.run_interactive_flows()
        assert context == {}
        # Template with direct interactive flow only
        mock_interactive_flow.run.return_value = self._ANY_INTERACTIVE_FLOW_CONTEXT
        mock_plugin.interactive_flow = None
        t = Template(location=self._ANY_LOCATION, interactive_flows=[mock_interactive_flow], plugins=[mock_plugin])
        context = t.run_interactive_flows()
        mock_interactive_flow.run.assert_called_once()
        assert context == self._ANY_INTERACTIVE_FLOW_CONTEXT
        # Template with direct interactive flow and a plugin's interactive flow
        mock_interactive_flow.reset_mock()
        mock_plugin.interactive_flow = MagicMock()
        mock_plugin.interactive_flow.run.return_value = self._ANY_PLUGIN_INTERACTIVE_FLOW_CONTEXT
        t = Template(location=self._ANY_LOCATION, interactive_flows=[mock_interactive_flow], plugins=[mock_plugin])
        context = t.run_interactive_flows()
        mock_interactive_flow.run.assert_called_once()
        mock_plugin.interactive_flow.run.assert_called_once()
        assert context == self._ANY_PLUGIN_INTERACTIVE_FLOW_CONTEXT

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
        t.generate_project(context=self._ANY_INTERACTIVE_FLOW_CONTEXT)
        mock_interactive_flow.run.assert_not_called()
        mock_preprocessor.run.assert_called_once_with(self._ANY_INTERACTIVE_FLOW_CONTEXT)
        mock_cookiecutter.assert_called_with(
            template=self._ANY_LOCATION, output_dir=".", no_input=True, extra_context=self._ANY_PROCESSOR_CONTEXT
        )
        mock_postprocessor.run.assert_called_once_with(self._ANY_PROCESSOR_CONTEXT)

    @patch("samcli.lib.cookiecutter.processor")
    @patch("samcli.lib.cookiecutter.processor")
    def test_generate_project_processors_exceptions(self, mock_preprocessor, mock_postprocessor):
        t = Template(
            location=self._ANY_LOCATION, preprocessors=[mock_preprocessor], postprocessors=[mock_postprocessor]
        )
        with self.assertRaises(GenerateProjectFailedError):
            mock_preprocessor.run.side_effect = Exception("something went wrong")
            t.generate_project({})
        mock_preprocessor.reset_mock()
        with self.assertRaises(GenerateProjectFailedError):
            mock_postprocessor.run.side_effect = Exception("something went wrong")
            t.generate_project({})

    @patch("samcli.lib.cookiecutter.template.generate_non_cookiecutter_project")
    @patch("samcli.lib.cookiecutter.template.cookiecutter")
    def test_generate_project_cookiecutter_exceptions(self, mock_cookiecutter, mock_generate_non_cookiecutter_project):
        t = Template(location=self._ANY_LOCATION)
        with self.assertRaises(InvalidLocationError):
            mock_cookiecutter.side_effect = UnknownRepoType()
            t.generate_project({})
        mock_cookiecutter.reset_mock()
        mock_cookiecutter.side_effect = RepositoryNotFound()
        t.generate_project({})
        mock_generate_non_cookiecutter_project.assert_called_once()
