from unittest import TestCase
from unittest.mock import Mock, MagicMock, patch

from samcli.lib.iac.interface import LookupPathType, ProjectTypes, LookupPath
from samcli.lib.iac.utils.helpers import get_iac_plugin, inject_iac_plugin


class TestGetIacPlugin(TestCase):
    @patch("samcli.lib.iac.utils.helpers.CfnIacPlugin")
    def test_get_iac_plugin_cfn_with_build(self, CfnIacPluginMock):
        cfn_iac_plugin_mock = Mock()
        cfn_iac_plugin_mock.get_project = Mock()
        cfn_iac_plugin_mock.get_project.return_value = Mock()
        CfnIacPluginMock.return_value = cfn_iac_plugin_mock
        command_params = MagicMock()
        command_params.get.return_value = "some_build_dir"

        iac_plugin, project = get_iac_plugin(ProjectTypes.CFN.value, command_params, True)
        CfnIacPluginMock.assert_called_once_with(command_params)
        self.assertEqual(iac_plugin, cfn_iac_plugin_mock)
        self.assertEqual(project, cfn_iac_plugin_mock.get_project.return_value)

    @patch("samcli.lib.iac.utils.helpers.CdkPlugin")
    def test_get_iac_plugin_cdk_with_build(self, CdkIacPluginMock):
        cdk_iac_plugin_mock = Mock()
        cdk_iac_plugin_mock.get_project = Mock()
        cdk_iac_plugin_mock.get_project.return_value = Mock()
        CdkIacPluginMock.return_value = cdk_iac_plugin_mock
        command_params = MagicMock()
        command_params.get.return_value = "some_build_dir"

        iac_plugin, project = get_iac_plugin(ProjectTypes.CDK.value, command_params, True)
        CdkIacPluginMock.assert_called_once_with(command_params)
        self.assertEqual(iac_plugin, cdk_iac_plugin_mock)
        self.assertEqual(project, cdk_iac_plugin_mock.get_project.return_value)


class TestInjectIacPlugin(TestCase):
    @patch("samcli.lib.iac.utils.helpers.get_iac_plugin")
    def test_inject_iac_plugin_cfn_with_build(self, get_iac_plugin_mock):
        iac_plugin_mock = Mock()
        project_mock = Mock()
        get_iac_plugin_mock.return_value = (iac_plugin_mock, project_mock)

        @inject_iac_plugin(True)
        def func(*args, **kwargs):
            return kwargs

        result = func(project_type=ProjectTypes.CFN.value)

        get_iac_plugin_mock.assert_called_once_with(
            ProjectTypes.CFN.value,
            {
                "project_type": ProjectTypes.CFN.value,
                "iac": iac_plugin_mock,
                "project": project_mock,
            },
            True,
        )
        self.assertEqual(
            result,
            {
                "project_type": ProjectTypes.CFN.value,
                "iac": iac_plugin_mock,
                "project": project_mock,
            },
        )
