import os
from unittest import TestCase
from unittest.mock import patch, Mock, ANY

from parameterized import parameterized

from samcli.local.lambdafn.exceptions import ResourceNotFound
from samcli.commands.build.build_context import BuildContext
from samcli.commands.build.exceptions import InvalidBuildDirException, MissingBuildMethodException


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
        resources_to_build = context.resources_to_build
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

        func_provider_mock = Mock()
        func_provider_mock.get_all.return_value = [func1, func2, func3_skipped, func4_skipped]
        funcprovider = SamFunctionProviderMock.return_value = func_provider_mock

        layer1 = DummyLayer("layer1", "buildMethod")
        layer2_skipped = DummyLayer("layer1", None)
        layer3_skipped = DummyLayer("layer1", "buildMethod", codeuri="packaged_function.zip")

        layer_provider_mock = Mock()
        layer_provider_mock.get_all.return_value = [layer1, layer2_skipped, layer3_skipped]
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
        self.assertEqual(resources_to_build.functions, [func1, func2])
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


class DummyLayer:
    def __init__(self, name, build_method, codeuri="layer_src"):
        self.name = name
        self.build_method = build_method
        self.codeuri = codeuri
        self.full_path = Mock()


class DummyFunction:
    def __init__(self, name, layers=[], inlinecode=None, codeuri="src"):
        self.name = name
        self.layers = layers
        self.inlinecode = inlinecode
        self.codeuri = codeuri
        self.full_path = Mock()
