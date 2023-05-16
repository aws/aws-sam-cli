"""
Unit tests for build command utils
"""
from unittest import TestCase
from unittest.mock import patch

from samcli.commands.build.utils import prompt_user_to_enable_mount_with_write_if_needed
from samcli.lib.utils.architecture import X86_64
from samcli.lib.utils.packagetype import ZIP, IMAGE
from samcli.lib.providers.provider import ResourcesToBuildCollector, Function, LayerVersion


class TestBuildUtils(TestCase):
    @patch("samcli.commands.build.utils.prompt")
    def test_must_prompt_for_layer(self, prompt_mock):
        base_dir = "/mybase"

        # dotnet6 need write permissions
        metadata1 = {"BuildMethod": "dotnet6"}
        metadata2 = {"BuildMethod": "python3.8"}
        layer1 = LayerVersion(
            "layer1",
            codeuri="codeuri",
            metadata=metadata1,
        )
        layer2 = LayerVersion(
            "layer2",
            codeuri="codeuri",
            metadata=metadata2,
        )

        function = Function(
            stack_path="somepath",
            function_id="function_id",
            name="logical_id",
            functionname="function_name",
            runtime="python3.8",
            memory=1234,
            timeout=12,
            handler="handler",
            codeuri="codeuri",
            environment=None,
            rolearn=None,
            layers=[layer1, layer2],
            events=None,
            metadata={},
            inlinecode=None,
            imageuri=None,
            imageconfig=None,
            packagetype=ZIP,
            architectures=[X86_64],
            codesign_config_arn=None,
            function_url_config=None,
            runtime_management_config=None,
        )

        resources_to_build = ResourcesToBuildCollector()
        resources_to_build.add_function(function)
        resources_to_build.add_layers([layer1, layer2])

        prompt_user_to_enable_mount_with_write_if_needed(resources_to_build, base_dir)

        prompt_mock.assert_called()

    @patch("samcli.commands.build.utils.prompt")
    def test_must_prompt_for_function(self, prompt_mock):
        base_dir = "/mybase"

        metadata = {"BuildMethod": "python3.8"}
        layer1 = LayerVersion(
            "layer1",
            codeuri="codeuri",
            metadata=metadata,
        )
        layer2 = LayerVersion(
            "layer2",
            codeuri="codeuri",
            metadata=metadata,
        )

        function = Function(
            stack_path="somepath",
            function_id="function_id",
            name="logical_id",
            functionname="function_name",
            runtime="dotnet6",
            memory=1234,
            timeout=12,
            handler="handler",
            codeuri="codeuri",
            environment=None,
            rolearn=None,
            layers=[layer1, layer2],
            events=None,
            metadata=None,
            inlinecode=None,
            imageuri=None,
            imageconfig=None,
            packagetype=ZIP,
            architectures=[X86_64],
            codesign_config_arn=None,
            function_url_config=None,
            runtime_management_config=None,
        )

        resources_to_build = ResourcesToBuildCollector()
        resources_to_build.add_function(function)
        resources_to_build.add_layers([layer1, layer2])

        prompt_user_to_enable_mount_with_write_if_needed(resources_to_build, base_dir)

        prompt_mock.assert_called()

    @patch("samcli.commands.build.utils.prompt")
    def test_must_prompt_for_function_with_specified_workflow(self, prompt_mock):
        base_dir = "/mybase"

        metadata1 = {"BuildMethod": "python3.8"}
        layer1 = LayerVersion(
            "layer1",
            codeuri="codeuri",
            metadata=metadata1,
        )
        layer2 = LayerVersion(
            "layer2",
            codeuri="codeuri",
            metadata=metadata1,
        )

        metadata2 = {"BuildMethod": "dotnet7"}

        function = Function(
            stack_path="somepath",
            function_id="function_id",
            name="logical_id",
            functionname="function_name",
            runtime="provided.al2",
            memory=1234,
            timeout=12,
            handler="handler",
            codeuri="codeuri",
            environment=None,
            rolearn=None,
            layers=[layer1, layer2],
            events=None,
            metadata=metadata2,
            inlinecode=None,
            imageuri=None,
            imageconfig=None,
            packagetype=ZIP,
            architectures=[X86_64],
            codesign_config_arn=None,
            function_url_config=None,
            runtime_management_config=None,
        )

        resources_to_build = ResourcesToBuildCollector()
        resources_to_build.add_function(function)
        resources_to_build.add_layers([layer1, layer2])

        prompt_user_to_enable_mount_with_write_if_needed(resources_to_build, base_dir)

        prompt_mock.assert_called()

    @patch("samcli.commands.build.utils.prompt")
    def test_must_not_prompt_for_image_function(self, prompt_mock):
        base_dir = "/mybase"

        metadata = {"BuildMethod": "python3.8"}
        layer1 = LayerVersion(
            "layer1",
            codeuri="codeuri",
            metadata=metadata,
        )
        layer2 = LayerVersion(
            "layer2",
            codeuri="codeuri",
            metadata=metadata,
        )

        function = Function(
            stack_path="somepath",
            function_id="function_id",
            name="logical_id",
            functionname="function_name",
            runtime="dotnet6",
            memory=1234,
            timeout=12,
            handler="handler",
            codeuri="codeuri",
            environment=None,
            rolearn=None,
            layers=[layer1, layer2],
            events=None,
            metadata=None,
            inlinecode=None,
            imageuri=None,
            imageconfig=None,
            packagetype=IMAGE,
            architectures=[X86_64],
            codesign_config_arn=None,
            function_url_config=None,
            runtime_management_config=None,
        )

        resources_to_build = ResourcesToBuildCollector()
        resources_to_build.add_function(function)
        resources_to_build.add_layers([layer1, layer2])

        prompt_user_to_enable_mount_with_write_if_needed(resources_to_build, base_dir)

        prompt_mock.assert_not_called()

    @patch("samcli.commands.build.utils.prompt")
    def test_must_not_prompt(self, prompt_mock):
        base_dir = "/mybase"

        metadata = {"BuildMethod": "python3.8"}
        layer1 = LayerVersion(
            "layer1",
            codeuri="codeuri",
            metadata=metadata,
        )
        layer2 = LayerVersion(
            "layer2",
            codeuri="codeuri",
            metadata=metadata,
        )

        function = Function(
            stack_path="somepath",
            function_id="function_id",
            name="logical_id",
            functionname="function_name",
            runtime="python3.8",
            memory=1234,
            timeout=12,
            handler="handler",
            codeuri="codeuri",
            environment=None,
            rolearn=None,
            layers=[layer1, layer2],
            events=None,
            metadata=None,
            inlinecode=None,
            imageuri=None,
            imageconfig=None,
            packagetype=ZIP,
            architectures=[X86_64],
            codesign_config_arn=None,
            function_url_config=None,
            runtime_management_config=None,
        )

        resources_to_build = ResourcesToBuildCollector()
        resources_to_build.add_function(function)
        resources_to_build.add_layers([layer1, layer2])

        prompt_user_to_enable_mount_with_write_if_needed(resources_to_build, base_dir)
        mount_with_write = prompt_user_to_enable_mount_with_write_if_needed(resources_to_build, base_dir)
        prompt_mock.assert_not_called()
        self.assertFalse(mount_with_write)
