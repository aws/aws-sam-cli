import os
from unittest import TestCase

import click
from unittest.mock import patch, MagicMock, Mock

from samcli.lib.iac.interface import ProjectTypes
from samcli.lib.iac.utils.iac_project_resolver import IacProjectResolver


def _make_ctx_params_side_effect_func(params):
    def side_effect(key, default=None):
        return params.get(key, default)

    return side_effect


def _find_in_paths_side_effect_func(paths):
    def side_effect(path):
        if path in paths:
            return True
        return False

    return side_effect


class TestProjectTypeResolver(TestCase):
    @patch("samcli.lib.iac.utils.iac_project_resolver.os.path.exists")
    def test_raise_error_if_detected_not_match_inputted(self, os_path_exist_mock):
        params = {"project_type": "CDK"}
        context_mock = MagicMock()
        context_mock.params.get.side_effect = _make_ctx_params_side_effect_func(params)

        include_build = True
        mock_template_exist_path = ["template.yaml"]
        os_path_exist_mock.side_effect = _find_in_paths_side_effect_func(mock_template_exist_path)

        projector_validator = IacProjectResolver(context_mock)
        with self.assertRaises(click.BadOptionUsage) as ex:
            projector_validator.resolve_project(include_build)
        self.assertEqual(ex.exception.option_name, "--project-type")
        self.assertEqual(
            ex.exception.message, "It seems your project type is CFN. However, you specified CDK in --project-type"
        )

    @patch("samcli.lib.iac.utils.iac_project_resolver.os.path.exists")
    def test_return_detected_project_type_without_default(self, os_path_exist_mock):
        context_mock = MagicMock()

        include_build = True
        mock_template_exist_path = ["cdk.json"]
        os_path_exist_mock.side_effect = _find_in_paths_side_effect_func(mock_template_exist_path)
        expected_project_type = "CDK"

        projector_validator = IacProjectResolver(context_mock)
        self.assertEqual(projector_validator._get_project_type(None, include_build), expected_project_type)

    @patch("samcli.lib.iac.utils.iac_project_resolver.os.path.exists")
    def test_return_detected_project_type_with_default(self, os_path_exist_mock):
        context_mock = MagicMock()

        include_build = True
        mock_template_exist_path = ["cdk.json"]
        os_path_exist_mock.side_effect = _find_in_paths_side_effect_func(mock_template_exist_path)
        expected_project_type = "CDK"
        provided_project_type = "CDK"

        projector_validator = IacProjectResolver(context_mock)
        self.assertEqual(
            projector_validator._get_project_type(provided_project_type, include_build), expected_project_type
        )

    @patch("samcli.lib.iac.utils.iac_project_resolver.os.path.exists")
    def test_detect_cfn_project_type(self, os_path_exist_mock):
        context_mock = MagicMock()

        include_build = True
        mock_template_exist_path = [os.path.join(".aws-sam", "build", "template.yaml")]
        os_path_exist_mock.side_effect = _find_in_paths_side_effect_func(mock_template_exist_path)
        projector_validator = IacProjectResolver(context_mock)
        self.assertEqual(projector_validator._detect_project_type(include_build), "CFN")

    @patch("samcli.lib.iac.utils.iac_project_resolver.os.path.exists")
    def test_return_cdk_project_type(self, os_path_exist_mock):
        context_mock = MagicMock()

        include_build = False
        mock_template_exist_path = ["cdk.json"]
        os_path_exist_mock.side_effect = _find_in_paths_side_effect_func(mock_template_exist_path)
        projector_validator = IacProjectResolver(context_mock)
        self.assertEqual(projector_validator._detect_project_type(include_build), "CDK")

    @patch("samcli.lib.iac.utils.iac_project_resolver.os.path.exists")
    def test_return_default_project_type(self, os_path_exist_mock):
        context_mock = MagicMock()

        include_build = True
        mock_template_exist_path = []
        os_path_exist_mock.side_effect = _find_in_paths_side_effect_func(mock_template_exist_path)
        projector_validator = IacProjectResolver(context_mock)
        self.assertEqual(projector_validator._detect_project_type(include_build), "CFN")


class TestGetIacPlugin(TestCase):
    @patch("samcli.lib.iac.utils.iac_project_resolver.CfnIacPlugin")
    def test_get_iac_plugin_cfn_with_build(self, CfnIacPluginMock):
        cfn_iac_plugin_mock = Mock()
        cfn_iac_plugin_mock.get_project = Mock()
        cfn_iac_plugin_mock.get_project.return_value = Mock()
        CfnIacPluginMock.return_value = cfn_iac_plugin_mock
        command_params = MagicMock()
        command_params.get.return_value = "some_build_dir"

        iac_plugin, project = IacProjectResolver.get_iac_plugin(
            ProjectTypes.CFN.value,
            command_params,
            True,
        )
        CfnIacPluginMock.assert_called_once_with(command_params)
        self.assertEqual(iac_plugin, cfn_iac_plugin_mock)
        self.assertEqual(project, cfn_iac_plugin_mock.get_project.return_value)

    @patch("samcli.lib.iac.utils.iac_project_resolver.CdkPlugin")
    def test_get_iac_plugin_cdk_with_build(self, CdkIacPluginMock):
        cdk_iac_plugin_mock = Mock()
        cdk_iac_plugin_mock.get_project = Mock()
        cdk_iac_plugin_mock.get_project.return_value = Mock()
        CdkIacPluginMock.return_value = cdk_iac_plugin_mock
        command_params = MagicMock()
        command_params.get.return_value = "some_build_dir"

        iac_plugin, project = IacProjectResolver.get_iac_plugin(
            ProjectTypes.CDK.value,
            command_params,
            True,
        )
        CdkIacPluginMock.assert_called_once_with(command_params)
        self.assertEqual(iac_plugin, cdk_iac_plugin_mock)
        self.assertEqual(project, cdk_iac_plugin_mock.get_project.return_value)
