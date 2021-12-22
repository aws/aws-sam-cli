import os
from unittest import TestCase
from unittest.mock import patch, Mock, ANY, call

from parameterized import parameterized

from samcli.lib.build.build_graph import DEFAULT_DEPENDENCIES_DIR
from samcli.lib.utils.osutils import BUILD_DIR_PERMISSIONS
from samcli.lib.utils.packagetype import ZIP, IMAGE
from samcli.local.lambdafn.exceptions import ResourceNotFound
from samcli.commands.build.build_context import BuildContext
from samcli.commands.build.exceptions import InvalidBuildDirException, MissingBuildMethodException
from samcli.commands.exceptions import UserException
from samcli.lib.build.app_builder import (
    BuildError,
    UnsupportedBuilderLibraryVersionError,
    BuildInsideContainerError,
    ContainerBuildNotSupported,
    ApplicationBuildResult,
)
from samcli.lib.build.workflow_config import UnsupportedRuntimeException
from samcli.local.lambdafn.exceptions import FunctionNotFound


class DeepWrap(Exception):
    pass


class TestBuildContext__enter__(TestCase):
    @patch("samcli.commands.build.build_context.SamLocalStackProvider.get_stacks")
    @patch("samcli.commands.build.build_context.SamFunctionProvider")
    @patch("samcli.commands.build.build_context.SamLayerProvider")
    @patch("samcli.commands.build.build_context.pathlib")
    @patch("samcli.commands.build.build_context.ContainerManager")
    def test_must_setup_context(
        self,
        ContainerManagerMock,
        pathlib_mock,
        SamLayerProviderMock,
        SamFunctionProviderMock,
        get_buildable_stacks_mock,
    ):
        template_dict = "template dict"
        stack = Mock()
        stack.template_dict = template_dict
        get_buildable_stacks_mock.return_value = ([stack], [])

        layer1 = DummyLayer("layer1", "buildmethod")
        layer2 = DummyLayer("layer1", None)
        layer_provider_mock = Mock()
        layer_provider_mock.get.return_value = layer1
        layerprovider = SamLayerProviderMock.return_value = layer_provider_mock

        function1 = DummyFunction("func1")
        func_provider_mock = Mock()
        func_provider_mock.get.return_value = function1
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
            parameter_overrides={"overrides": "value"},
            skip_pull_image=True,
            mode="buildmode",
            cached=False,
            cache_dir="cache_dir",
            parallel=True,
            aws_region="any_aws_region",
        )
        setup_build_dir_mock = Mock()
        build_dir_result = setup_build_dir_mock.return_value = "my/new/build/dir"
        context._setup_build_dir = setup_build_dir_mock

        # call the enter method
        result = context.__enter__()

        self.assertEqual(result, context)  # __enter__ must return self
        self.assertEqual(context.function_provider, funcprovider)
        self.assertEqual(context.layer_provider, layerprovider)
        self.assertEqual(context.base_dir, base_dir)
        self.assertEqual(context.container_manager, container_mgr_mock)
        self.assertEqual(context.build_dir, build_dir_result)
        self.assertEqual(context.use_container, True)
        self.assertEqual(context.stacks, [stack])
        self.assertEqual(context.manifest_path_override, os.path.abspath("manifest_path"))
        self.assertEqual(context.mode, "buildmode")
        resources_to_build = context.get_resources_to_build()
        self.assertTrue(function1 in resources_to_build.functions)
        self.assertTrue(layer1 in resources_to_build.layers)

        get_buildable_stacks_mock.assert_called_once_with(
            "template_file",
            parameter_overrides={"overrides": "value"},
            global_parameter_overrides={"AWS::Region": "any_aws_region"},
        )
        SamFunctionProviderMock.assert_called_once_with([stack], False)
        pathlib_mock.Path.assert_called_once_with("template_file")
        setup_build_dir_mock.assert_called_with("build_dir", True)
        ContainerManagerMock.assert_called_once_with(docker_network_id="network", skip_pull_image=True)
        func_provider_mock.get.assert_called_once_with("function_identifier")

    @patch("samcli.commands.build.build_context.SamLocalStackProvider.get_stacks")
    @patch("samcli.commands.build.build_context.SamFunctionProvider")
    @patch("samcli.commands.build.build_context.SamLayerProvider")
    @patch("samcli.commands.build.build_context.pathlib")
    @patch("samcli.commands.build.build_context.ContainerManager")
    def test_must_fail_with_illegal_identifier(
        self,
        ContainerManagerMock,
        pathlib_mock,
        SamLayerProviderMock,
        SamFunctionProviderMock,
        get_buildable_stacks_mock,
    ):
        template_dict = "template dict"
        stack = Mock()
        stack.template_dict = template_dict
        get_buildable_stacks_mock.return_value = ([stack], [])
        func_provider_mock = Mock()
        func_provider_mock.get.return_value = None
        func_provider_mock.get_all.return_value = [DummyFunction("func1"), DummyFunction("func2")]
        funcprovider = SamFunctionProviderMock.return_value = func_provider_mock

        layer_provider_mock = Mock()
        layer_provider_mock.get.return_value = None
        layer_provider_mock.get_all.return_value = [DummyLayer("layer1", None), DummyLayer("layer2", None)]
        layerprovider = SamLayerProviderMock.return_value = layer_provider_mock

        base_dir = pathlib_mock.Path.return_value.resolve.return_value.parent = "basedir"
        container_mgr_mock = ContainerManagerMock.return_value = Mock()

        context = BuildContext(
            "illegal",
            "template_file",
            None,  # No base dir is provided
            "build_dir",
            manifest_path="manifest_path",
            clean=True,
            use_container=True,
            docker_network="network",
            parameter_overrides={"overrides": "value"},
            skip_pull_image=True,
            mode="buildmode",
            cached=False,
            cache_dir="cache_dir",
            parallel=True,
        )
        setup_build_dir_mock = Mock()
        build_dir_result = setup_build_dir_mock.return_value = "my/new/build/dir"
        context._setup_build_dir = setup_build_dir_mock

        # call the enter method
        result = context.__enter__()
        with self.assertRaises(ResourceNotFound):
            context.resources_to_build

    @patch("samcli.commands.build.build_context.SamLocalStackProvider.get_stacks")
    @patch("samcli.commands.build.build_context.SamFunctionProvider")
    @patch("samcli.commands.build.build_context.SamLayerProvider")
    @patch("samcli.commands.build.build_context.pathlib")
    @patch("samcli.commands.build.build_context.ContainerManager")
    def test_must_return_only_layer_when_layer_is_build(
        self,
        ContainerManagerMock,
        pathlib_mock,
        SamLayerProviderMock,
        SamFunctionProviderMock,
        get_buildable_stacks_mock,
    ):
        template_dict = "template dict"
        stack = Mock()
        stack.template_dict = template_dict
        get_buildable_stacks_mock.return_value = ([stack], [])
        func_provider_mock = Mock()
        func_provider_mock.get.return_value = None
        funcprovider = SamFunctionProviderMock.return_value = func_provider_mock

        layer1 = DummyLayer("layer1", "python3.8")
        layer_provider_mock = Mock()
        layer_provider_mock.get.return_value = layer1
        layerprovider = SamLayerProviderMock.return_value = layer_provider_mock

        base_dir = pathlib_mock.Path.return_value.resolve.return_value.parent = "basedir"
        container_mgr_mock = ContainerManagerMock.return_value = Mock()

        context = BuildContext(
            "layer1",
            "template_file",
            None,  # No base dir is provided
            "build_dir",
            manifest_path="manifest_path",
            clean=True,
            use_container=True,
            docker_network="network",
            parameter_overrides={"overrides": "value"},
            skip_pull_image=True,
            mode="buildmode",
            cached=False,
            cache_dir="cache_dir",
            parallel=True,
        )
        setup_build_dir_mock = Mock()
        build_dir_result = setup_build_dir_mock.return_value = "my/new/build/dir"
        context._setup_build_dir = setup_build_dir_mock

        # call the enter method
        context.__enter__()
        self.assertTrue(layer1 in context.resources_to_build.layers)

    @patch("samcli.commands.build.build_context.SamLocalStackProvider.get_stacks")
    @patch("samcli.commands.build.build_context.SamFunctionProvider")
    @patch("samcli.commands.build.build_context.SamLayerProvider")
    @patch("samcli.commands.build.build_context.pathlib")
    @patch("samcli.commands.build.build_context.ContainerManager")
    def test_must_return_buildable_dependent_layer_when_function_is_build(
        self,
        ContainerManagerMock,
        pathlib_mock,
        SamLayerProviderMock,
        SamFunctionProviderMock,
        get_buildable_stacks_mock,
    ):
        template_dict = "template dict"
        stack = Mock()
        stack.template_dict = template_dict
        get_buildable_stacks_mock.return_value = ([stack], [])

        layer1 = DummyLayer("layer1", "python3.8")
        layer2 = DummyLayer("layer2", None)
        layer_provider_mock = Mock()
        layer_provider_mock.get.return_value = layer1
        layerprovider = SamLayerProviderMock.return_value = layer_provider_mock

        func1 = DummyFunction("func1", [layer1, layer2])
        func_provider_mock = Mock()
        func_provider_mock.get.return_value = func1
        funcprovider = SamFunctionProviderMock.return_value = func_provider_mock

        base_dir = pathlib_mock.Path.return_value.resolve.return_value.parent = "basedir"
        container_mgr_mock = ContainerManagerMock.return_value = Mock()

        context = BuildContext(
            "func1",
            "template_file",
            None,  # No base dir is provided
            "build_dir",
            manifest_path="manifest_path",
            clean=True,
            use_container=True,
            docker_network="network",
            parameter_overrides={"overrides": "value"},
            skip_pull_image=True,
            mode="buildmode",
            cached=False,
            cache_dir="cache_dir",
            parallel=True,
        )
        setup_build_dir_mock = Mock()
        build_dir_result = setup_build_dir_mock.return_value = "my/new/build/dir"
        context._setup_build_dir = setup_build_dir_mock

        # call the enter method
        context.__enter__()
        self.assertTrue(func1 in context.resources_to_build.functions)
        self.assertTrue(layer1 in context.resources_to_build.layers)
        self.assertTrue(layer2 not in context.resources_to_build.layers)
        self.assertTrue(context.is_building_specific_resource)

    @patch("samcli.commands.build.build_context.SamLocalStackProvider.get_stacks")
    @patch("samcli.commands.build.build_context.SamFunctionProvider")
    @patch("samcli.commands.build.build_context.SamLayerProvider")
    @patch("samcli.commands.build.build_context.pathlib")
    @patch("samcli.commands.build.build_context.ContainerManager")
    def test_must_fail_when_layer_is_build_without_buildmethod(
        self,
        ContainerManagerMock,
        pathlib_mock,
        SamLayerProviderMock,
        SamFunctionProviderMock,
        get_buildable_stacks_mock,
    ):
        template_dict = "template dict"
        stack = Mock()
        stack.template_dict = template_dict
        get_buildable_stacks_mock.return_value = ([stack], [])
        func_provider_mock = Mock()
        func_provider_mock.get.return_value = None
        funcprovider = SamFunctionProviderMock.return_value = func_provider_mock

        layer1 = DummyLayer("layer1", None)
        layer_provider_mock = Mock()
        layer_provider_mock.get.return_value = layer1
        layerprovider = SamLayerProviderMock.return_value = layer_provider_mock

        base_dir = pathlib_mock.Path.return_value.resolve.return_value.parent = "basedir"
        container_mgr_mock = ContainerManagerMock.return_value = Mock()

        context = BuildContext(
            "layer1",
            "template_file",
            None,  # No base dir is provided
            "build_dir",
            manifest_path="manifest_path",
            clean=True,
            use_container=True,
            docker_network="network",
            parameter_overrides={"overrides": "value"},
            skip_pull_image=True,
            mode="buildmode",
            cached=False,
            cache_dir="cache_dir",
            parallel=True,
        )
        setup_build_dir_mock = Mock()
        build_dir_result = setup_build_dir_mock.return_value = "my/new/build/dir"
        context._setup_build_dir = setup_build_dir_mock

        # call the enter method
        result = context.__enter__()
        with self.assertRaises(MissingBuildMethodException):
            context.resources_to_build

    @patch("samcli.commands.build.build_context.SamLocalStackProvider.get_stacks")
    @patch("samcli.commands.build.build_context.SamFunctionProvider")
    @patch("samcli.commands.build.build_context.SamLayerProvider")
    @patch("samcli.commands.build.build_context.pathlib")
    @patch("samcli.commands.build.build_context.ContainerManager")
    def test_must_return_many_functions_to_build(
        self,
        ContainerManagerMock,
        pathlib_mock,
        SamLayerProviderMock,
        SamFunctionProviderMock,
        get_buildable_stacks_mock,
    ):
        """
        In this unit test, we also verify
        - inlinecode functions are skipped
        - functions with codeuri pointing to a zip file are skipped
        - layers without build method are skipped
        - layers with codeuri pointing to a zip file are skipped
        """
        template_dict = "template dict"
        stack = Mock()
        stack.template_dict = template_dict
        get_buildable_stacks_mock.return_value = ([stack], [])
        func1 = DummyFunction("func1")
        func2 = DummyFunction("func2")
        func3_skipped = DummyFunction("func3", inlinecode="def handler(): pass", codeuri=None)
        func4_skipped = DummyFunction("func4", codeuri="packaged_function.zip")
        func5_skipped = DummyFunction("func5", codeuri=None, packagetype=IMAGE)
        func6 = DummyFunction(
            "func6", packagetype=IMAGE, metadata={"DockerContext": "/path", "Dockerfile": "DockerFile"}
        )
        func7_skipped = DummyFunction("func7", skip_build=True)

        func_provider_mock = Mock()
        func_provider_mock.get_all.return_value = [
            func1,
            func2,
            func3_skipped,
            func4_skipped,
            func5_skipped,
            func6,
            func7_skipped,
        ]
        funcprovider = SamFunctionProviderMock.return_value = func_provider_mock

        layer1 = DummyLayer("layer1", "buildMethod")
        layer2_skipped = DummyLayer("layer1", None)
        layer3_skipped = DummyLayer("layer1", "buildMethod", codeuri="packaged_function.zip")
        layer4_skipped = DummyLayer("layer4", "buildMethod", skip_build=True)

        layer_provider_mock = Mock()
        layer_provider_mock.get_all.return_value = [layer1, layer2_skipped, layer3_skipped, layer4_skipped]
        layerprovider = SamLayerProviderMock.return_value = layer_provider_mock

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
            parameter_overrides={"overrides": "value"},
            skip_pull_image=True,
            mode="buildmode",
            cached=False,
            cache_dir="cache_dir",
            parallel=True,
        )
        setup_build_dir_mock = Mock()
        build_dir_result = setup_build_dir_mock.return_value = "my/new/build/dir"
        context._setup_build_dir = setup_build_dir_mock

        # call the enter method
        result = context.__enter__()

        self.assertEqual(result, context)  # __enter__ must return self
        self.assertEqual(context.function_provider, funcprovider)
        self.assertEqual(context.layer_provider, layerprovider)
        self.assertEqual(context.base_dir, base_dir)
        self.assertEqual(context.container_manager, container_mgr_mock)
        self.assertEqual(context.build_dir, build_dir_result)
        self.assertEqual(context.use_container, True)
        self.assertEqual(context.stacks, [stack])
        self.assertEqual(context.manifest_path_override, os.path.abspath("manifest_path"))
        self.assertEqual(context.mode, "buildmode")
        self.assertFalse(context.is_building_specific_resource)
        resources_to_build = context.resources_to_build
        self.assertEqual(resources_to_build.functions, [func1, func2, func6])
        self.assertEqual(resources_to_build.layers, [layer1])
        get_buildable_stacks_mock.assert_called_once_with(
            "template_file", parameter_overrides={"overrides": "value"}, global_parameter_overrides=None
        )
        SamFunctionProviderMock.assert_called_once_with([stack], False)
        pathlib_mock.Path.assert_called_once_with("template_file")
        setup_build_dir_mock.assert_called_with("build_dir", True)
        ContainerManagerMock.assert_called_once_with(docker_network_id="network", skip_pull_image=True)
        func_provider_mock.get_all.assert_called_once()

    @parameterized.expand([(["remote_stack_1", "stack.remote_stack_2"], "print_warning"), ([], False)])
    @patch("samcli.commands.build.build_context.LOG")
    @patch("samcli.commands.build.build_context.SamLocalStackProvider.get_stacks")
    @patch("samcli.commands.build.build_context.SamFunctionProvider")
    @patch("samcli.commands.build.build_context.SamLayerProvider")
    @patch("samcli.commands.build.build_context.pathlib")
    @patch("samcli.commands.build.build_context.ContainerManager")
    def test_must_print_remote_url_warning(
        self,
        remote_stack_full_paths,
        print_warning,
        ContainerManagerMock,
        pathlib_mock,
        SamLayerProviderMock,
        SamFunctionProviderMock,
        get_buildable_stacks_mock,
        log_mock,
    ):
        get_buildable_stacks_mock.return_value = ([], remote_stack_full_paths)

        context = BuildContext(
            "function_identifier",
            "template_file",
            None,  # No base dir is provided
            "build_dir",
            manifest_path="manifest_path",
            clean=True,
            use_container=True,
            docker_network="network",
            parameter_overrides={"overrides": "value"},
            skip_pull_image=True,
            mode="buildmode",
            cached=False,
            cache_dir="cache_dir",
            parallel=True,
        )
        context._setup_build_dir = Mock()

        # call the enter method
        context.__enter__()
        if print_warning:
            log_mock.warning.assert_called_once_with(
                ANY, "\n".join([f"- {full_path}" for full_path in remote_stack_full_paths])
            )
        else:
            log_mock.warning.assert_not_called()


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


class TestBuildContext_setup_cached_and_deps_dir(TestCase):
    @parameterized.expand([(True,), (False,)])
    @patch("samcli.commands.build.build_context.pathlib.Path")
    @patch("samcli.commands.build.build_context.SamLocalStackProvider")
    @patch("samcli.commands.build.build_context.SamFunctionProvider")
    @patch("samcli.commands.build.build_context.SamLayerProvider")
    def test_cached_dir_and_deps_dir_creation(
        self, cached, patched_layer, patched_function, patched_stack, patched_path
    ):
        patched_stack.get_stacks.return_value = ([], None)
        build_context = BuildContext(
            resource_identifier="function_identifier",
            template_file="template_file",
            base_dir="base_dir",
            build_dir="build_dir",
            cache_dir="cache_dir",
            parallel=False,
            mode="mode",
            cached=cached,
        )

        with patch.object(build_context, "_setup_build_dir"):
            build_context.set_up()

            call_assertion = lambda: patched_path.assert_has_calls(
                [
                    call("cache_dir"),
                    call().mkdir(exist_ok=True, mode=BUILD_DIR_PERMISSIONS, parents=True),
                    call(DEFAULT_DEPENDENCIES_DIR),
                    call().mkdir(exist_ok=True, mode=BUILD_DIR_PERMISSIONS, parents=True),
                ],
                any_order=True,
            )

            # if it is cached validate calls above is made,
            # otherwise validate an assertion will be raised since they are not called
            if cached:
                call_assertion()
            else:
                with self.assertRaises(AssertionError):
                    call_assertion()


class TestBuildContext_run(TestCase):
    @patch("samcli.commands.build.build_context.SamLocalStackProvider.get_stacks")
    @patch("samcli.commands.build.build_context.SamFunctionProvider")
    @patch("samcli.commands.build.build_context.SamLayerProvider")
    @patch("samcli.commands.build.build_context.pathlib")
    @patch("samcli.commands.build.build_context.ContainerManager")
    @patch("samcli.commands.build.build_context.BuildContext._setup_build_dir")
    @patch("samcli.commands.build.build_context.ApplicationBuilder")
    @patch("samcli.commands.build.build_context.BuildContext.get_resources_to_build")
    @patch("samcli.commands.build.build_context.move_template")
    @patch("samcli.commands.build.build_context.os")
    def test_run_build_context(
        self,
        os_mock,
        move_template_mock,
        resources_mock,
        ApplicationBuilderMock,
        build_dir_mock,
        ContainerManagerMock,
        pathlib_mock,
        SamLayerProviderMock,
        SamFunctionProviderMock,
        get_buildable_stacks_mock,
    ):

        root_stack = Mock()
        root_stack.is_root_stack = True
        auto_dependency_layer = False
        root_stack.get_output_template_path = Mock(return_value="./build_dir/template.yaml")
        child_stack = Mock()
        child_stack.get_output_template_path = Mock(return_value="./build_dir/abcd/template.yaml")
        stack_output_template_path_by_stack_path = {
            root_stack.stack_path: "./build_dir/template.yaml",
            child_stack.stack_path: "./build_dir/abcd/template.yaml",
        }
        resources_mock.return_value = Mock()

        builder_mock = ApplicationBuilderMock.return_value = Mock()
        artifacts = "artifacts"
        builder_mock.build.return_value = ApplicationBuildResult(Mock(), artifacts)
        modified_template_root = "modified template 1"
        modified_template_child = "modified template 2"
        builder_mock.update_template.side_effect = [modified_template_root, modified_template_child]

        get_buildable_stacks_mock.return_value = ([root_stack, child_stack], [])
        layer1 = DummyLayer("layer1", "python3.8")
        layer_provider_mock = Mock()
        layer_provider_mock.get.return_value = layer1
        layerprovider = SamLayerProviderMock.return_value = layer_provider_mock
        func1 = DummyFunction("func1", [layer1])
        func_provider_mock = Mock()
        func_provider_mock.get.return_value = func1
        funcprovider = SamFunctionProviderMock.return_value = func_provider_mock
        base_dir = pathlib_mock.Path.return_value.resolve.return_value.parent = "basedir"
        container_mgr_mock = ContainerManagerMock.return_value = Mock()
        build_dir_mock.return_value = "build_dir"

        with BuildContext(
            resource_identifier="function_identifier",
            template_file="template_file",
            base_dir="base_dir",
            build_dir="build_dir",
            cache_dir="cache_dir",
            cached=False,
            clean="clean",
            use_container=False,
            parallel="parallel",
            parameter_overrides="parameter_overrides",
            manifest_path="manifest_path",
            docker_network="docker_network",
            skip_pull_image="skip_pull_image",
            mode="mode",
            container_env_var={},
            container_env_var_file=None,
            build_images={},
            create_auto_dependency_layer=auto_dependency_layer,
        ) as build_context:
            build_context.run()

            ApplicationBuilderMock.assert_called_once_with(
                ANY,
                build_context.build_dir,
                build_context.base_dir,
                build_context.cache_dir,
                build_context.cached,
                build_context.is_building_specific_resource,
                manifest_path_override=build_context.manifest_path_override,
                container_manager=build_context.container_manager,
                mode=build_context.mode,
                parallel=build_context._parallel,
                container_env_var=build_context._container_env_var,
                container_env_var_file=build_context._container_env_var_file,
                build_images=build_context._build_images,
                combine_dependencies=not auto_dependency_layer,
            )
            builder_mock.build.assert_called_once()
            builder_mock.update_template.assert_has_calls(
                [
                    call(
                        root_stack,
                        artifacts,
                        stack_output_template_path_by_stack_path,
                    )
                ],
                [
                    call(
                        child_stack,
                        artifacts,
                        stack_output_template_path_by_stack_path,
                    )
                ],
            )
            move_template_mock.assert_has_calls(
                [
                    call(
                        root_stack.location,
                        stack_output_template_path_by_stack_path[root_stack.stack_path],
                        modified_template_root,
                    ),
                    call(
                        child_stack.location,
                        stack_output_template_path_by_stack_path[child_stack.stack_path],
                        modified_template_child,
                    ),
                ]
            )

    @parameterized.expand(
        [
            (UnsupportedRuntimeException(), "UnsupportedRuntimeException"),
            (BuildInsideContainerError(), "BuildInsideContainerError"),
            (BuildError(wrapped_from=DeepWrap().__class__.__name__, msg="Test"), "DeepWrap"),
            (ContainerBuildNotSupported(), "ContainerBuildNotSupported"),
            (
                UnsupportedBuilderLibraryVersionError(container_name="name", error_msg="msg"),
                "UnsupportedBuilderLibraryVersionError",
            ),
        ]
    )
    @patch("samcli.commands.build.build_context.SamLocalStackProvider.get_stacks")
    @patch("samcli.commands.build.build_context.SamFunctionProvider")
    @patch("samcli.commands.build.build_context.SamLayerProvider")
    @patch("samcli.commands.build.build_context.pathlib")
    @patch("samcli.commands.build.build_context.ContainerManager")
    @patch("samcli.commands.build.build_context.BuildContext._setup_build_dir")
    @patch("samcli.commands.build.build_context.ApplicationBuilder")
    @patch("samcli.commands.build.build_context.BuildContext.get_resources_to_build")
    @patch("samcli.commands.build.build_context.move_template")
    @patch("samcli.commands.build.build_context.os")
    def test_must_catch_known_exceptions(
        self,
        exception,
        wrapped_exception,
        os_mock,
        move_template_mock,
        resources_mock,
        ApplicationBuilderMock,
        build_dir_mock,
        ContainerManagerMock,
        pathlib_mock,
        SamLayerProviderMock,
        SamFunctionProviderMock,
        get_buildable_stacks_mock,
    ):

        stack = Mock()
        resources_mock.return_value = Mock()

        builder_mock = ApplicationBuilderMock.return_value = Mock()
        artifacts = builder_mock.build.return_value = "artifacts"
        modified_template_root = "modified template 1"
        modified_template_child = "modified template 2"
        builder_mock.update_template.side_effect = [modified_template_root, modified_template_child]

        get_buildable_stacks_mock.return_value = ([stack], [])
        layer1 = DummyLayer("layer1", "python3.8")
        layer_provider_mock = Mock()
        layer_provider_mock.get.return_value = layer1
        layerprovider = SamLayerProviderMock.return_value = layer_provider_mock
        func1 = DummyFunction("func1", [layer1])
        func_provider_mock = Mock()
        func_provider_mock.get.return_value = func1
        funcprovider = SamFunctionProviderMock.return_value = func_provider_mock
        base_dir = pathlib_mock.Path.return_value.resolve.return_value.parent = "basedir"
        container_mgr_mock = ContainerManagerMock.return_value = Mock()
        build_dir_mock.return_value = "build_dir"

        builder_mock.build.side_effect = exception

        with self.assertRaises(UserException) as ctx:
            with BuildContext(
                resource_identifier="function_identifier",
                template_file="template_file",
                base_dir="base_dir",
                build_dir="build_dir",
                cache_dir="cache_dir",
                cached=False,
                clean="clean",
                use_container=False,
                parallel="parallel",
                parameter_overrides="parameter_overrides",
                manifest_path="manifest_path",
                docker_network="docker_network",
                skip_pull_image="skip_pull_image",
                mode="mode",
                container_env_var={},
                container_env_var_file=None,
                build_images={},
            ) as build_context:
                build_context.run()

        self.assertEqual(str(ctx.exception), str(exception))
        self.assertEqual(wrapped_exception, ctx.exception.wrapped_from)

    @patch("samcli.commands.build.build_context.SamLocalStackProvider.get_stacks")
    @patch("samcli.commands.build.build_context.SamFunctionProvider")
    @patch("samcli.commands.build.build_context.SamLayerProvider")
    @patch("samcli.commands.build.build_context.pathlib")
    @patch("samcli.commands.build.build_context.ContainerManager")
    @patch("samcli.commands.build.build_context.BuildContext._setup_build_dir")
    @patch("samcli.commands.build.build_context.ApplicationBuilder")
    @patch("samcli.commands.build.build_context.BuildContext.get_resources_to_build")
    @patch("samcli.commands.build.build_context.move_template")
    @patch("samcli.commands.build.build_context.os")
    def test_must_catch_function_not_found_exception(
        self,
        os_mock,
        move_template_mock,
        resources_mock,
        ApplicationBuilderMock,
        build_dir_mock,
        ContainerManagerMock,
        pathlib_mock,
        SamLayerProviderMock,
        SamFunctionProviderMock,
        get_buildable_stacks_mock,
    ):
        stack = Mock()
        resources_mock.return_value = Mock()

        builder_mock = ApplicationBuilderMock.return_value = Mock()
        artifacts = builder_mock.build.return_value = "artifacts"
        modified_template_root = "modified template 1"
        modified_template_child = "modified template 2"
        builder_mock.update_template.side_effect = [modified_template_root, modified_template_child]

        get_buildable_stacks_mock.return_value = ([stack], [])
        layer1 = DummyLayer("layer1", "python3.8")
        layer_provider_mock = Mock()
        layer_provider_mock.get.return_value = layer1
        layerprovider = SamLayerProviderMock.return_value = layer_provider_mock
        func1 = DummyFunction("func1", [layer1])
        func_provider_mock = Mock()
        func_provider_mock.get.return_value = func1
        funcprovider = SamFunctionProviderMock.return_value = func_provider_mock
        base_dir = pathlib_mock.Path.return_value.resolve.return_value.parent = "basedir"
        container_mgr_mock = ContainerManagerMock.return_value = Mock()
        build_dir_mock.return_value = "build_dir"

        ApplicationBuilderMock.side_effect = FunctionNotFound("Function Not Found")

        with self.assertRaises(UserException) as ctx:
            with BuildContext(
                resource_identifier="function_identifier",
                template_file="template_file",
                base_dir="base_dir",
                build_dir="build_dir",
                cache_dir="cache_dir",
                cached=False,
                clean="clean",
                use_container=False,
                parallel="parallel",
                parameter_overrides="parameter_overrides",
                manifest_path="manifest_path",
                docker_network="docker_network",
                skip_pull_image="skip_pull_image",
                mode="mode",
                container_env_var={},
                container_env_var_file=None,
                build_images={},
            ) as build_context:
                build_context.run()

        self.assertEqual(str(ctx.exception), "Function Not Found")


class DummyLayer:
    def __init__(self, name, build_method, codeuri="layer_src", skip_build=False):
        self.name = name
        self.build_method = build_method
        self.codeuri = codeuri
        self.full_path = Mock()
        self.skip_build = skip_build


class DummyFunction:
    def __init__(
        self,
        name,
        layers=[],
        inlinecode=None,
        codeuri="src",
        imageuri="image:latest",
        packagetype=ZIP,
        metadata=None,
        skip_build=False,
    ):
        self.name = name
        self.layers = layers
        self.inlinecode = inlinecode
        self.codeuri = codeuri
        self.imageuri = imageuri
        self.full_path = Mock()
        self.packagetype = packagetype
        self.metadata = metadata if metadata else {}
        self.skip_build = skip_build
