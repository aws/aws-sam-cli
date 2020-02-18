import os
from unittest import TestCase
from unittest.mock import patch, Mock

from samcli.commands.build.build_context import BuildContext
from samcli.commands.build.exceptions import InvalidBuildDirException


class TestBuildContext__enter__(TestCase):
    @patch("samcli.commands.build.build_context.get_template_data")
    @patch("samcli.commands.build.build_context.SamFunctionProvider")
    @patch("samcli.commands.build.build_context.pathlib")
    @patch("samcli.commands.build.build_context.ContainerManager")
    def test_must_setup_context(
        self, ContainerManagerMock, pathlib_mock, SamFunctionProviderMock, get_template_data_mock
    ):

        template_dict = get_template_data_mock.return_value = "template dict"
        func_provider_mock = Mock()
        func_provider_mock.get.return_value = "function to build"
        funcprovider = SamFunctionProviderMock.return_value = func_provider_mock
        base_dir = pathlib_mock.Path.return_value.resolve.return_value.parent = "basedir"
        container_mgr_mock = ContainerManagerMock.return_value = Mock()

        context = BuildContext(
            "function_identifier",
            "template_file",
            None,  # No base dir is provided
            "build_dir",
            manifest_path="manifest_path",
            clean=True,
            use_container=True,
            docker_network="network",
            parameter_overrides="overrides",
            skip_pull_image=True,
            mode="buildmode",
        )
        setup_build_dir_mock = Mock()
        build_dir_result = setup_build_dir_mock.return_value = "my/new/build/dir"
        context._setup_build_dir = setup_build_dir_mock

        # call the enter method
        result = context.__enter__()

        self.assertEqual(result, context)  # __enter__ must return self
        self.assertEqual(context.template_dict, template_dict)
        self.assertEqual(context.function_provider, funcprovider)
        self.assertEqual(context.base_dir, base_dir)
        self.assertEqual(context.container_manager, container_mgr_mock)
        self.assertEqual(context.build_dir, build_dir_result)
        self.assertEqual(context.use_container, True)
        self.assertEqual(context.output_template_path, os.path.join(build_dir_result, "template.yaml"))
        self.assertEqual(context.manifest_path_override, os.path.abspath("manifest_path"))
        self.assertEqual(context.mode, "buildmode")
        self.assertEqual(context.functions_to_build, ["function to build"])

        get_template_data_mock.assert_called_once_with("template_file")
        SamFunctionProviderMock.assert_called_once_with(template_dict, "overrides")
        pathlib_mock.Path.assert_called_once_with("template_file")
        setup_build_dir_mock.assert_called_with("build_dir", True)
        ContainerManagerMock.assert_called_once_with(docker_network_id="network", skip_pull_image=True)
        func_provider_mock.get.assert_called_once_with("function_identifier")

    @patch("samcli.commands.build.build_context.get_template_data")
    @patch("samcli.commands.build.build_context.SamFunctionProvider")
    @patch("samcli.commands.build.build_context.pathlib")
    @patch("samcli.commands.build.build_context.ContainerManager")
    def test_must_return_many_functions_to_build(
        self, ContainerManagerMock, pathlib_mock, SamFunctionProviderMock, get_template_data_mock
    ):
        template_dict = get_template_data_mock.return_value = "template dict"
        func_provider_mock = Mock()
        func_provider_mock.get_all.return_value = ["function to build", "and another function"]
        funcprovider = SamFunctionProviderMock.return_value = func_provider_mock
        base_dir = pathlib_mock.Path.return_value.resolve.return_value.parent = "basedir"
        container_mgr_mock = ContainerManagerMock.return_value = Mock()

        context = BuildContext(
            None,
            "template_file",
            None,  # No base dir is provided
            "build_dir",
            manifest_path="manifest_path",
            clean=True,
            use_container=True,
            docker_network="network",
            parameter_overrides="overrides",
            skip_pull_image=True,
            mode="buildmode",
        )
        setup_build_dir_mock = Mock()
        build_dir_result = setup_build_dir_mock.return_value = "my/new/build/dir"
        context._setup_build_dir = setup_build_dir_mock

        # call the enter method
        result = context.__enter__()

        self.assertEqual(result, context)  # __enter__ must return self
        self.assertEqual(context.template_dict, template_dict)
        self.assertEqual(context.function_provider, funcprovider)
        self.assertEqual(context.base_dir, base_dir)
        self.assertEqual(context.container_manager, container_mgr_mock)
        self.assertEqual(context.build_dir, build_dir_result)
        self.assertEqual(context.use_container, True)
        self.assertEqual(context.output_template_path, os.path.join(build_dir_result, "template.yaml"))
        self.assertEqual(context.manifest_path_override, os.path.abspath("manifest_path"))
        self.assertEqual(context.mode, "buildmode")
        self.assertEqual(context.functions_to_build, ["function to build", "and another function"])

        get_template_data_mock.assert_called_once_with("template_file")
        SamFunctionProviderMock.assert_called_once_with(template_dict, "overrides")
        pathlib_mock.Path.assert_called_once_with("template_file")
        setup_build_dir_mock.assert_called_with("build_dir", True)
        ContainerManagerMock.assert_called_once_with(docker_network_id="network", skip_pull_image=True)
        func_provider_mock.get_all.assert_called_once()


class TestBuildContext_setup_build_dir(TestCase):
    @patch("samcli.commands.build.build_context.shutil")
    @patch("samcli.commands.build.build_context.os")
    @patch("samcli.commands.build.build_context.pathlib")
    def test_build_dir_exists_with_non_empty_dir(self, pathlib_patch, os_patch, shutil_patch):
        path_mock = Mock()
        pathlib_patch.Path.return_value = path_mock
        os_patch.path.abspath.side_effect = ["/somepath", "/cwd/path"]
        path_mock.cwd.return_value = "/cwd/path"
        os_patch.listdir.return_value = True
        path_mock.resolve.return_value = "long/full/path"
        path_mock.exists.return_value = True
        build_dir = "/somepath"

        full_build_path = BuildContext._setup_build_dir(build_dir, True)

        self.assertEqual(full_build_path, "long/full/path")
        self.assertEqual(os_patch.path.abspath.call_count, 2)

        os_patch.listdir.assert_called_once()
        path_mock.exists.assert_called_once()
        path_mock.mkdir.assert_called_once_with(mode=0o755, parents=True, exist_ok=True)
        pathlib_patch.Path.assert_called_once_with(build_dir)
        shutil_patch.rmtree.assert_called_once_with(build_dir)
        pathlib_patch.Path.cwd.assert_called_once()

    @patch("samcli.commands.build.build_context.shutil")
    @patch("samcli.commands.build.build_context.os")
    @patch("samcli.commands.build.build_context.pathlib")
    def test_build_dir_exists_with_empty_dir(self, pathlib_patch, os_patch, shutil_patch):
        path_mock = Mock()
        pathlib_patch.Path.return_value = path_mock
        os_patch.listdir.return_value = False
        os_patch.path.abspath.side_effect = ["/somepath", "/cwd/path"]
        path_mock.cwd.return_value = "/cwd/path"
        path_mock.resolve.return_value = "long/full/path"
        path_mock.exists.return_value = True
        build_dir = "/somepath"

        full_build_path = BuildContext._setup_build_dir(build_dir, True)

        self.assertEqual(full_build_path, "long/full/path")
        self.assertEqual(os_patch.path.abspath.call_count, 2)

        os_patch.listdir.assert_called_once()
        path_mock.exists.assert_called_once()
        path_mock.mkdir.assert_called_once_with(mode=0o755, parents=True, exist_ok=True)
        pathlib_patch.Path.assert_called_once_with(build_dir)
        shutil_patch.rmtree.assert_not_called()
        pathlib_patch.Path.cwd.assert_called_once()

    @patch("samcli.commands.build.build_context.shutil")
    @patch("samcli.commands.build.build_context.os")
    @patch("samcli.commands.build.build_context.pathlib")
    def test_build_dir_does_not_exist(self, pathlib_patch, os_patch, shutil_patch):
        path_mock = Mock()
        pathlib_patch.Path.return_value = path_mock
        os_patch.path.abspath.side_effect = ["/somepath", "/cwd/path"]
        path_mock.cwd.return_value = "/cwd/path"
        path_mock.resolve.return_value = "long/full/path"
        path_mock.exists.return_value = False
        build_dir = "/somepath"

        full_build_path = BuildContext._setup_build_dir(build_dir, True)

        self.assertEqual(full_build_path, "long/full/path")
        self.assertEqual(os_patch.path.abspath.call_count, 2)

        os_patch.listdir.assert_not_called()
        path_mock.exists.assert_called_once()
        path_mock.mkdir.assert_called_once_with(mode=0o755, parents=True, exist_ok=True)
        pathlib_patch.Path.assert_called_once_with(build_dir)
        shutil_patch.rmtree.assert_not_called()
        pathlib_patch.Path.cwd.assert_called_once()

    @patch("samcli.commands.build.build_context.shutil")
    @patch("samcli.commands.build.build_context.os")
    @patch("samcli.commands.build.build_context.pathlib")
    def test_non_clean_build_when_dir_exists_with_non_empty_dir(self, pathlib_patch, os_patch, shutil_patch):
        path_mock = Mock()
        pathlib_patch.Path.return_value = path_mock
        os_patch.path.abspath.side_effect = ["/somepath", "/cwd/path"]
        path_mock.cwd.return_value = "/cwd/path"
        os_patch.listdir.return_value = True
        path_mock.resolve.return_value = "long/full/path"
        path_mock.exists.return_value = True
        build_dir = "/somepath"

        full_build_path = BuildContext._setup_build_dir(build_dir, False)

        self.assertEqual(full_build_path, "long/full/path")
        self.assertEqual(os_patch.path.abspath.call_count, 2)

        os_patch.listdir.assert_called_once()
        path_mock.exists.assert_called_once()
        path_mock.mkdir.assert_called_once_with(mode=0o755, parents=True, exist_ok=True)
        pathlib_patch.Path.assert_called_once_with(build_dir)
        shutil_patch.rmtree.assert_not_called()
        pathlib_patch.Path.cwd.assert_called_once()

    @patch("samcli.commands.build.build_context.shutil")
    @patch("samcli.commands.build.build_context.os")
    @patch("samcli.commands.build.build_context.pathlib")
    def test_when_build_dir_is_cwd_raises_exception(self, pathlib_patch, os_patch, shutil_patch):
        path_mock = Mock()
        pathlib_patch.Path.return_value = path_mock
        os_patch.path.abspath.side_effect = ["/somepath", "/somepath"]
        path_mock.cwd.return_value = "/somepath"
        build_dir = "/somepath"

        with self.assertRaises(InvalidBuildDirException):
            BuildContext._setup_build_dir(build_dir, True)

            self.assertEqual(os_patch.path.abspath.call_count, 2)

        os_patch.listdir.assert_not_called()
        path_mock.exists.assert_not_called()
        path_mock.mkdir.assert_not_called()
        pathlib_patch.Path.assert_called_once_with(build_dir)
        shutil_patch.rmtree.assert_not_called()
        pathlib_patch.Path.cwd.assert_called_once()
