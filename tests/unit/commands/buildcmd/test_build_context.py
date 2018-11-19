import os

from unittest import TestCase
from mock import patch, Mock

from samcli.commands.build.build_context import BuildContext


class TestBuildContext__enter__(TestCase):

    @patch("samcli.commands.build.build_context.get_template_data")
    @patch("samcli.commands.build.build_context.SamFunctionProvider")
    @patch("samcli.commands.build.build_context.pathlib")
    @patch("samcli.commands.build.build_context.ContainerManager")
    def test_must_setup_context(self, ContainerManagerMock, pathlib_mock, SamFunctionProviderMock,
                                get_template_data_mock):

        template_dict = get_template_data_mock.return_value = "template dict"
        funcprovider = SamFunctionProviderMock.return_value = "funcprovider"
        base_dir = pathlib_mock.Path.return_value.resolve.return_value.parent = "basedir"
        container_mgr_mock = ContainerManagerMock.return_value = Mock()

        context = BuildContext("template_file",
                               None,  # No base dir is provided
                               "build_dir",
                               manifest_path="manifest_path",
                               clean=True,
                               use_container=True,
                               docker_network="network",
                               parameter_overrides="overrides",
                               skip_pull_image=True)
        setup_build_dir_mock = Mock()
        build_dir_result = setup_build_dir_mock.return_value = "my/new/build/dir"
        context._setup_build_dir = setup_build_dir_mock

        # call the enter method
        result = context.__enter__()

        self.assertEquals(result, context)  # __enter__ must return self
        self.assertEquals(context.template_dict, template_dict)
        self.assertEquals(context.function_provider, funcprovider)
        self.assertEquals(context.base_dir, base_dir)
        self.assertEquals(context.container_manager, container_mgr_mock)
        self.assertEquals(context.build_dir, build_dir_result)
        self.assertEquals(context.use_container, True)
        self.assertEquals(context.output_template_path, os.path.join(build_dir_result, "template.yaml"))
        self.assertEquals(context.manifest_path_override, os.path.abspath("manifest_path"))

        get_template_data_mock.assert_called_once_with("template_file")
        SamFunctionProviderMock.assert_called_once_with(template_dict, "overrides")
        pathlib_mock.Path.assert_called_once_with("template_file")
        setup_build_dir_mock.assert_called_with("build_dir", True)
        ContainerManagerMock.assert_called_once_with(docker_network_id="network",
                                                     skip_pull_image=True)
