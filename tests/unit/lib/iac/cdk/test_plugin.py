import os
from samcli.commands._utils.template import TemplateFormat
import shutil
import subprocess
from pathlib import Path
from typing import Dict, Mapping

from unittest import TestCase
from unittest.mock import ANY, Mock, mock_open, patch

from samcli.lib.iac.interface import (
    DictSection,
    Project,
    LookupPath,
    LookupPathType,
    Resource,
    S3Asset,
    ImageAsset,
    SimpleSection,
    Stack,
)
from samcli.lib.iac.cdk.plugin import (
    CdkPlugin,
    _collect_assets,
    _write_stack,
    _shallow_clone_asset,
    _undo_normalize_resource_metadata,
    _collect_stack_assets,
    _update_built_artifacts,
    _collect_project_assets,
    _update_asset_params_default_values,
    _get_cdk_executable_path,
)
from samcli.lib.iac.cdk.exceptions import CdkToolkitNotInstalledError, InvalidCloudAssemblyError
from samcli.lib.iac.cdk.constants import (
    MANIFEST_FILENAME,
    TREE_FILENAME,
    OUT_FILENAME,
)

from tests.unit.lib.iac.cdk.helper import read_json_file

CLOUD_ASSEMBLY_DIR = os.path.join(os.path.dirname(__file__), "test_data", "cdk.out")


class TestCdkPlugin(TestCase):
    def setUp(self) -> None:
        self.command_params = {"cdk_app": CLOUD_ASSEMBLY_DIR}
        # self.cdk_synth_mock =
        # self.plugin = CdkPlugin(context)
        # self.project = self.plugin.get_project([LookupPath(os.path.dirname(__file__), LookupPathType.SOURCE)])

    @patch("os.path.isfile", return_value=True)
    @patch("os.path.abspath", return_value="/path/to/cloud_assemble")
    @patch("os.path.exists", return_value=True)
    def test_get_project_build_type_lookup_path(self, path_exists_mock, abspath_mock, is_file_mock):
        cdk_plugin = CdkPlugin(self.command_params)
        cdk_plugin._get_project_from_cloud_assembly = Mock()
        cdk_plugin._get_project_from_cloud_assembly.return_value = Project(stacks=[Mock(), Mock()])

        project = cdk_plugin.get_project([LookupPath("lookup/path", LookupPathType.BUILD)])
        cdk_plugin._get_project_from_cloud_assembly.assert_called_once_with(abspath_mock.return_value)
        self.assertIsInstance(project, Project)
        self.assertEqual(len(project.stacks), 2)

    @patch("os.path.isfile", return_value=True)
    @patch("os.path.abspath", return_value="/path/to/cloud_assemble")
    @patch("os.path.exists", return_value=True)
    def test_get_project_source_type_lookup_path(self, path_exists_mock, abspath_mock, is_file_mock):
        cdk_plugin = CdkPlugin(self.command_params)
        cdk_plugin._get_project_from_cloud_assembly = Mock()
        cdk_plugin._get_project_from_cloud_assembly.return_value = Project(stacks=[Mock(), Mock()])
        cdk_plugin._cdk_synth = Mock()
        cdk_plugin._cdk_synth.return_value = abspath_mock.return_value

        project = cdk_plugin.get_project([LookupPath("lookup/path", LookupPathType.SOURCE)])
        cdk_plugin._cdk_synth.assert_called_once_with(app=CLOUD_ASSEMBLY_DIR, context=None)
        cdk_plugin._get_project_from_cloud_assembly.assert_called_once_with(abspath_mock.return_value)
        self.assertIsInstance(project, Project)
        self.assertEqual(len(project.stacks), 2)

    @patch("os.path.isfile", return_value=True)
    def test_get_project_invalid_lookup_path(self, is_file_mock):
        cdk_plugin = CdkPlugin(self.command_params)

        with self.assertRaises(InvalidCloudAssemblyError):
            cdk_plugin.get_project([])

    @patch("shutil.copy2")
    @patch("samcli.lib.iac.cdk.plugin._update_built_artifacts")
    @patch("samcli.lib.iac.cdk.plugin._write_stack")
    def test_write_project(self, write_stack_mock, update_built_artifacts_mock, copy2_mock):
        cdk_plugin = CdkPlugin(self.command_params)
        project_mock = Mock()
        project_mock.stacks = [Mock()]
        build_dir = "build_dir"
        cdk_plugin.write_project(project_mock, build_dir)

        self.assertEqual(copy2_mock.call_count, 3)

        update_built_artifacts_mock.assert_called_once_with(project_mock, cdk_plugin._cloud_assembly_dir, build_dir)
        for stack in project_mock.stacks:
            write_stack_mock.assert_called_once_with(stack, cdk_plugin._cloud_assembly_dir, build_dir)

    def test_should_update_property_after_package(self):
        asset = ImageAsset()
        cdk_plugin = CdkPlugin(self.command_params)
        self.assertTrue(cdk_plugin.should_update_property_after_package(asset))

    def test_should_not_update_property_after_package(self):
        asset = S3Asset()
        cdk_plugin = CdkPlugin(self.command_params)
        self.assertFalse(cdk_plugin.should_update_property_after_package(asset))

    @patch("samcli.lib.iac.cdk.plugin._update_asset_params_default_values")
    def test_update_asset_params_default_values_after_packaging(self, update_asset_params_default_values_mock):
        parameters_mock = {}

        def param_side_effect_1(asset, params):
            parameters_mock["foo"] = "bar"

        def param_side_efftec_2(stack, params):
            parameters_mock["bax"] = "baz"

        update_asset_params_default_values_mock.side_effect = param_side_effect_1

        stack_mock = Mock()
        resource_mock = Mock()
        stack_mock.get.return_value = {"resource": resource_mock}
        asset = S3Asset()
        asset.extra_details = {"assetParameters": {"param": "param"}}
        nested_stack_mock = Mock()
        resource_mock.nested_stack = nested_stack_mock
        resource_mock.assets = [asset]
        cdk_plugin = CdkPlugin(self.command_params)
        original_func = cdk_plugin.update_asset_params_default_values_after_packaging
        cdk_plugin.update_asset_params_default_values_after_packaging = Mock()
        cdk_plugin.update_asset_params_default_values_after_packaging.side_effect = param_side_efftec_2

        original_func(stack_mock, parameters_mock)
        update_asset_params_default_values_mock.assert_called_once_with(asset, parameters_mock)
        cdk_plugin.update_asset_params_default_values_after_packaging.assert_called_once_with(
            nested_stack_mock, parameters_mock
        )

        self.assertEqual(
            parameters_mock,
            {
                "foo": "bar",
                "bax": "baz",
            },
        )

    @patch("samcli.lib.iac.cdk.plugin._undo_normalize_resource_metadata")
    def test_update_resource_after_packaging(self, undo_normalize_resource_metadata_mock):
        resource_mock = Mock()
        asset_mock = S3Asset()
        asset_mock.extra_details = {"assetParameters": {"foo": "bar"}}
        resource_mock.assets = [asset_mock]

        cdk_plugin = CdkPlugin(self.command_params)
        cdk_plugin.update_resource_after_packaging(resource_mock)
        undo_normalize_resource_metadata_mock.assert_called_once_with(resource_mock)

    @patch("subprocess.check_output")
    @patch("os.path.isdir", return_value=False)
    @patch("samcli.lib.iac.cdk.plugin.copy_tree")
    @patch("samcli.lib.iac.cdk.plugin._get_cdk_executable_path", return_value="cdk")
    def test_cdk_synth_app_is_executable_with_context(
        self, get_cdk_executable_path_mock, copy_tree_mock, isdir_mock, check_output_mock
    ):
        cdk_plugin = CdkPlugin(self.command_params)
        app = "cdk_app_executable"
        context = ["key1=value1", "key2=value2"]
        cloud_assembly_dir = cdk_plugin._cdk_synth(app, context)
        check_output_mock.assert_called_once_with(
            [
                "cdk",
                "synth",
                "--no-staging",
                "--app",
                app,
                "-o",
                cdk_plugin._cloud_assembly_dir,
                "--context",
                context[0],
                "--context",
                context[1],
            ],
            stderr=subprocess.STDOUT,
        )
        copy_tree_mock.assert_not_called()
        self.assertEqual(cloud_assembly_dir, cdk_plugin._cloud_assembly_dir)

    @patch("subprocess.check_output")
    @patch("os.path.isdir", return_value=True)
    @patch("samcli.lib.iac.cdk.plugin.copy_tree")
    @patch("samcli.lib.iac.cdk.plugin._get_cdk_executable_path", return_value="cdk")
    def test_cdk_synth_app_is_dir(self, get_cdk_executable_path_mock, copy_tree_mock, isdir_mock, check_output_mock):
        cdk_plugin = CdkPlugin(self.command_params)
        app = "path/to/cloud_assembly"
        cloud_assembly_dir = cdk_plugin._cdk_synth(app)
        check_output_mock.assert_called_once_with(
            [
                "cdk",
                "synth",
                "--no-staging",
                "--app",
                app,
            ],
            stderr=subprocess.STDOUT,
        )
        copy_tree_mock.assert_called_once_with(app, cdk_plugin._cloud_assembly_dir)
        self.assertEqual(cloud_assembly_dir, cdk_plugin._cloud_assembly_dir)

    @patch("subprocess.check_output")
    @patch("os.path.isdir", return_value=False)
    @patch("samcli.lib.iac.cdk.plugin.copy_tree")
    @patch("samcli.lib.iac.cdk.plugin._get_cdk_executable_path", return_value="cdk")
    def test_cdk_synth_app_is_none(self, get_cdk_executable_path_mock, copy_tree_mock, isdir_mock, check_output_mock):
        cdk_plugin = CdkPlugin(self.command_params)
        app = None
        cloud_assembly_dir = cdk_plugin._cdk_synth(app)
        check_output_mock.assert_called_once_with(
            [
                "cdk",
                "synth",
                "--no-staging",
                "-o",
                cdk_plugin._cloud_assembly_dir,
            ],
            stderr=subprocess.STDOUT,
        )
        copy_tree_mock.assert_not_called()
        self.assertEqual(cloud_assembly_dir, cdk_plugin._cloud_assembly_dir)

    @patch("samcli.lib.iac.cdk.plugin.CloudAssembly")
    def test_get_project_from_cloud_assembly(self, cloud_assembly_class_mock):
        cloud_assembly_mock = Mock()
        cloud_assembly_mock.stacks = [Mock(), Mock()]
        cloud_assembly_class_mock.return_value = cloud_assembly_mock
        cdk_plugin = CdkPlugin(self.command_params)
        build_stack_mock = Mock()
        stack_mock1 = Mock()
        stack_mock2 = Mock()
        build_stack_mock.side_effect = [stack_mock1, stack_mock2]
        cdk_plugin._build_stack = build_stack_mock
        cloud_assembly_path = "path/to/cloud_assembly"
        project = cdk_plugin._get_project_from_cloud_assembly(cloud_assembly_path)
        cloud_assembly_class_mock.assert_called_once_with(cloud_assembly_path, cdk_plugin._source_dir)
        self.assertEqual(cdk_plugin._build_stack.call_count, 2)
        self.assertEqual(len(project.stacks), 2)

    @patch("samcli.lib.iac.cdk.plugin._collect_assets")
    def test_build_stack(self, collect_assets_mock):
        cloud_assembly_mock = Mock()
        ca_stack_mock = Mock()
        ca_stack_mock.template = {
            "Resources": {},
            "Parameters": {
                "Param1": {"Type": "String", "Default": "foo"},
            },
            "OtherMapping": {},
            "OtherKey": "other",
        }
        ca_stack_mock.stack_name = "test_stack"
        ca_stack_mock.template_file = "to/template"
        ca_stack_mock.template_full_path = "/path/to/template"
        s3_asset = S3Asset()
        image_asset = ImageAsset()
        assets = {"s3/asset": s3_asset, "image/asset": image_asset}
        collect_assets_mock.return_value = assets
        cdk_plugin = CdkPlugin(self.command_params)
        cdk_plugin._build_resources_section = Mock()
        stack = cdk_plugin._build_stack(cloud_assembly_mock, ca_stack_mock)
        cdk_plugin._build_resources_section.assert_called_once_with(assets, ca_stack_mock, cloud_assembly_mock, ANY, {})
        self.assertIsInstance(stack, Stack)
        self.assertEqual(stack.stack_id, "test_stack")
        self.assertEqual(stack.name, "test_stack")
        self.assertFalse(stack.is_nested, False)
        self.assertEqual(list(stack.sections.keys()), list(ca_stack_mock.template.keys()))
        self.assertIn("Param1", stack["Parameters"])

    def test_build_resource_section_image_asset(self):
        image_asset = ImageAsset()
        assets = {
            "/path/to/asset": image_asset,
        }
        dict_section = DictSection("Resources")
        section_dict = {
            "logical_id": {
                "Type": "Resource",
                "Properties": {
                    "some_prop": "value",
                },
                "Metadata": {
                    "aws:cdk:path": "stack/resouce",
                    "aws:asset:path": "/path/to/asset",
                    "aws:asset:property": "some_prop",
                    "aws:asset:local_image": "image:tag",
                },
            },
        }
        ca_stack_mock = Mock()
        ca_stack_mock.find_nested_stack_by_logical_id.return_value = None
        cloud_assembly_mock = Mock()
        node_mock = Mock()
        node_mock.id = "resource_id"
        node_mock.is_l2_construct_resource.return_value = False
        cloud_assembly_mock.tree.find_node_by_path.return_value = node_mock

        cdk_plugin = CdkPlugin(self.command_params)
        cdk_plugin._build_resources_section(assets, ca_stack_mock, cloud_assembly_mock, dict_section, section_dict)
        self.assertTrue("logical_id" in dict_section)
        resource = dict_section["logical_id"]
        self.assertIsInstance(resource, Resource)
        self.assertEqual(resource.key, "logical_id")
        self.assertEqual(resource.body, section_dict["logical_id"])
        self.assertEqual(resource.assets, [image_asset])
        self.assertEqual(resource["Properties"]["some_prop"], "image:tag")
        self.assertEqual(resource.item_id, "resource_id")

    def test_build_resource_section_nested_stack(self):
        nested_stack_asset = S3Asset()
        assets = {"/path/to/asset": nested_stack_asset}
        dict_section = DictSection("Resources")
        section_dict = {
            "logical_id": {
                "Type": "AWS::CloudFormation::Stack",
                "Properties": {
                    "some_prop": "value",
                },
                "Metadata": {
                    "aws:cdk:path": "stack/resouce",
                    "aws:asset:path": "/path/to/asset",
                    "aws:asset:property": "some_prop",
                },
            },
        }
        ca_stack_mock = Mock()
        ca_stack_mock.find_nested_stack_by_logical_id.return_value = ca_nested_stack_mock = Mock()
        cloud_assembly_mock = Mock()
        node_mock = Mock()
        node_mock.id = "resource_id"
        node_mock.is_l2_construct_resource.return_value = False
        cloud_assembly_mock.tree.find_node_by_path.return_value = node_mock

        cdk_plugin = CdkPlugin(self.command_params)
        cdk_plugin._build_stack = Mock()
        cdk_plugin._build_stack.return_value = Mock()
        cdk_plugin._build_resources_section(assets, ca_stack_mock, cloud_assembly_mock, dict_section, section_dict)
        self.assertTrue("logical_id" in dict_section)
        resource = dict_section["logical_id"]
        self.assertIsInstance(resource, Resource)
        self.assertEqual(resource.key, "logical_id")
        self.assertEqual(resource.body, section_dict["logical_id"])
        self.assertEqual(resource.assets, [nested_stack_asset])
        self.assertEqual(resource.item_id, "resource_id")
        self.assertEqual(resource["Properties"]["some_prop"], "/path/to/asset")

        cdk_plugin._build_stack.assert_called_once_with(cloud_assembly_mock, ca_nested_stack_mock)


class TestCollectAssets(TestCase):
    @patch("os.path.normpath", return_value="/path/to/asset")
    @patch("os.path.join", return_value="joined/path")
    def test_collect_assets(self, normpath_mock, join_mock):
        ca_assets = [
            {
                "repositoryName": "aws-cdk/assets",
                "imageTag": "8db62da8c9a661a051169ec5710e7c48e471f6eb556b9d853c77e0efd9689d7e",
                "id": "8db62da8c9a661a051169ec5710e7c48e471f6eb556b9d853c77e0efd9689d7e",
                "packaging": "container-image",
                "path": "asset.8db62da8c9a661a051169ec5710e7c48e471f6eb556b9d853c77e0efd9689d7e",
                "sourceHash": "8db62da8c9a661a051169ec5710e7c48e471f6eb556b9d853c77e0efd9689d7e",
            },
            {
                "path": "asset.97bd9d4f97345f890d541646ecd5ec0348b62d5618cedfd76a6f6dc94f2e4f0e",
                "id": "97bd9d4f97345f890d541646ecd5ec0348b62d5618cedfd76a6f6dc94f2e4f0e",
                "packaging": "zip",
                "sourceHash": "97bd9d4f97345f890d541646ecd5ec0348b62d5618cedfd76a6f6dc94f2e4f0e",
                "s3BucketParameter": "AssetParameters97bd9d4f97345f890d541646ecd5ec0348b62d5618cedfd76a6f6dc94f2e4f0eS3BucketDD3A7E9A",
                "s3KeyParameter": "AssetParameters97bd9d4f97345f890d541646ecd5ec0348b62d5618cedfd76a6f6dc94f2e4f0eS3VersionKeyCEC49660",
                "artifactHashParameter": "AssetParameters97bd9d4f97345f890d541646ecd5ec0348b62d5618cedfd76a6f6dc94f2e4f0eArtifactHashBD7218A6",
            },
        ]
        ca_stack_mock = Mock()
        ca_stack_mock.assets = ca_assets
        assets = _collect_assets(ca_stack_mock)
        self.assertIn("asset.8db62da8c9a661a051169ec5710e7c48e471f6eb556b9d853c77e0efd9689d7e", assets)
        self.assertIsInstance(
            assets["asset.8db62da8c9a661a051169ec5710e7c48e471f6eb556b9d853c77e0efd9689d7e"], ImageAsset
        )
        self.assertIn("asset.97bd9d4f97345f890d541646ecd5ec0348b62d5618cedfd76a6f6dc94f2e4f0e", assets)
        self.assertIsInstance(assets["asset.97bd9d4f97345f890d541646ecd5ec0348b62d5618cedfd76a6f6dc94f2e4f0e"], S3Asset)


class TestWriteStack(TestCase):
    def setUp(self):
        self.original_func = _write_stack

    @patch("os.path.join", side_effect=["src_template_path", "stack_build_location", "build_dir/nested_stack"])
    @patch("samcli.lib.iac.cdk.plugin._undo_normalize_resource_metadata")
    @patch("samcli.lib.iac.cdk.plugin.move_template")
    def test_write_stack_s3_asset(self, move_template_mock, undo_normalize_mock, path_join_mock):
        stack = Stack(stack_id="test_stack")
        stack["Resources"] = DictSection("Resources")
        stack.extra_details["template_file"] = "template_file"
        resource = Resource(
            "Function1",
            body={
                "Type": "AWS::Lambda::Function",
                "Properties": {},
                "Metadata": {
                    "aws:cdk:path": "stack/resouce",
                    "aws:asset:path": "source_asset",
                    "aws:asset:property": "Code",
                },
            },
        )
        stack["Resources"]["Function1"] = resource
        s3_asset = S3Asset(
            asset_id="id",
            updated_source_path="updated_source_path",
        )
        resource.assets.append(s3_asset)

        _write_stack(stack, "cloud_assembly_dir", "build_dir")
        undo_normalize_mock.assert_called_once_with(resource)
        self.assertEqual(resource["Metadata"]["aws:asset:path"], "updated_source_path")
        move_template_mock.assert_called_once_with(
            "src_template_path", "stack_build_location", stack, output_format=TemplateFormat.JSON
        )

    @patch("os.path.join", side_effect=["src_template_path", "stack_build_location", "build_dir/nested_stack"])
    @patch("samcli.lib.iac.cdk.plugin._undo_normalize_resource_metadata")
    @patch("samcli.lib.iac.cdk.plugin.move_template")
    def test_write_stack_image_asset(self, move_template_mock, undo_normalize_mock, path_join_mock):
        stack = Stack(stack_id="test_stack")
        stack["Resources"] = DictSection("Resources")
        stack.extra_details["template_file"] = "template_file"
        resource = Resource(
            "Function1",
            body={
                "Type": "AWS::Lambda::Function",
                "Properties": {},
                "Metadata": {
                    "aws:cdk:path": "stack/resouce",
                    "aws:asset:path": "source_asset",
                    "aws:asset:property": "Code",
                },
            },
        )
        stack["Resources"]["Function1"] = resource
        image_asset = ImageAsset(
            asset_id="id",
            source_local_image="image:tag",
        )
        resource.assets.append(image_asset)

        _write_stack(stack, "cloud_assembly_dir", "build_dir")
        undo_normalize_mock.assert_called_once_with(resource)
        self.assertIn("aws:asset:local_image", resource["Metadata"])
        self.assertEqual(resource["Metadata"]["aws:asset:local_image"], "image:tag")
        move_template_mock.assert_called_once_with(
            "src_template_path", "stack_build_location", stack, output_format=TemplateFormat.JSON
        )

    @patch("os.path.join", side_effect=["src_template_path", "stack_build_location", "build_dir/nested_stack"])
    @patch("samcli.lib.iac.cdk.plugin._undo_normalize_resource_metadata")
    @patch("samcli.lib.iac.cdk.plugin.move_template")
    @patch("samcli.lib.iac.cdk.plugin._write_stack")
    def test_write_stack_s3_asset_nested_stack(
        self, write_stack_mock, move_template_mock, undo_normalize_mock, path_join_mock
    ):
        stack = Stack(stack_id="test_stack")
        stack["Resources"] = DictSection("Resources")
        stack.extra_details["template_file"] = "template_file"
        resource = Resource(
            "NestedStack",
            body={
                "Type": "AWS::Lambda::Function",
                "Properties": {},
                "Metadata": {
                    "aws:cdk:path": "stack/resouce",
                    "aws:asset:path": "source_asset",
                    "aws:asset:property": "TemplateURL",
                },
            },
        )
        stack["Resources"]["Function1"] = resource
        s3_asset = S3Asset(
            asset_id="id",
            updated_source_path="updated_source_path",
            source_property="TemplateURL",
        )
        resource.assets.append(s3_asset)
        resource.nested_stack = Stack(
            sections={"Resources": {}}, extra_details={"template_file": "hello.nested-stack.json"}
        )

        self.original_func(stack, "cloud_assembly_dir", "build_dir")
        undo_normalize_mock.assert_called_once_with(resource)
        self.assertEqual(resource["Metadata"]["aws:asset:path"], "build_dir/nested_stack")
        self.assertEqual(s3_asset.updated_source_path, "build_dir/nested_stack")
        write_stack_mock.assert_called_once_with(resource.nested_stack, "cloud_assembly_dir", "build_dir")
        move_template_mock.assert_called_once_with(
            "src_template_path", "stack_build_location", stack, output_format=TemplateFormat.JSON
        )


class TestUndoNormalizeResourceMetadata(TestCase):
    def test_undo_normalize_resource_metadata(self):
        resource = Resource("Function")
        resource["Key"] = "NewVal"
        resource.extra_details["original_body"] = {"Key": "OriginalVal"}
        _undo_normalize_resource_metadata(resource)
        self.assertEqual(resource["Key"], "OriginalVal")


class TestCollectStackAssets(TestCase):
    def setUp(self):
        self.original_func = _collect_stack_assets

    def test_collect_stack_assets(self):
        s3_asset = S3Asset(asset_id="s3")
        image_asset = ImageAsset(asset_id="image")
        stack = Stack()
        dict_section = DictSection()
        dict_section["Function1"] = Resource(assets=[s3_asset])
        dict_section["Function2"] = Resource(assets=[image_asset])
        stack.sections["Resources"] = dict_section

        collected = _collect_stack_assets(stack)
        self.assertIn("s3", collected)
        self.assertIn("image", collected)
        self.assertEqual(collected["s3"], s3_asset)
        self.assertEqual(collected["image"], image_asset)

    @patch("samcli.lib.iac.cdk.plugin._collect_stack_assets")
    def test_collect_stack_assets_nested_stack(self, collect_stack_assets_mock):
        nested_stack_asset = S3Asset(asset_id="nested_stack")
        stack = Stack()
        dict_section = DictSection()
        nested_stack = Stack(sections={"Resources": {}})
        dict_section["NestedStack"] = Resource(assets=[nested_stack_asset], nested_stack=nested_stack)
        stack.sections["Resources"] = dict_section

        collected = self.original_func(stack)
        self.assertIn("nested_stack", collected)
        self.assertEqual(collected["nested_stack"], nested_stack_asset)
        collect_stack_assets_mock.assert_called_once_with(nested_stack)


class TestCollectProjectAssets(TestCase):
    @patch(
        "samcli.lib.iac.cdk.plugin._collect_stack_assets",
        side_effect=[{"1": S3Asset(asset_id="1")}, {"2": ImageAsset(asset_id="2")}],
    )
    def test_collect_project_assets(self, collect_stack_assets_mock):
        project = Project(stacks=[Stack(name="stack1"), Stack(name="stack2")])
        assets, root_stack_names = _collect_project_assets(project)
        self.assertIn("stack1", assets)
        self.assertIn("1", assets["stack1"])
        self.assertIn("stack2", assets)
        self.assertIn("2", assets["stack2"])
        self.assertIn("stack1", root_stack_names)
        self.assertIn("stack2", root_stack_names)


class TestShallowCloneAsset(TestCase):
    def test_shallow_clone_s3_asset(self):
        s3_asset = S3Asset()
        collected_s3_asset = S3Asset(
            source_path="collected_path",
            source_property="collected_property",
            updated_source_path="collected_updated_path",
            destinations=[Mock()],
            object_version="collected_version",
            object_key="colected_key",
            bucket_name="collected_bucket",
        )
        collected_assets = {"id": collected_s3_asset}
        _shallow_clone_asset(s3_asset, "id", collected_assets)
        self.assertNotEqual(s3_asset, collected_s3_asset)
        self.assertEqual(s3_asset.source_path, collected_s3_asset.source_path)
        self.assertEqual(s3_asset.source_property, collected_s3_asset.source_property)
        self.assertEqual(s3_asset.updated_source_path, collected_s3_asset.updated_source_path)
        self.assertEqual(s3_asset.destinations, collected_s3_asset.destinations)
        self.assertEqual(s3_asset.object_version, collected_s3_asset.object_version)
        self.assertEqual(s3_asset.object_key, collected_s3_asset.object_key)
        self.assertEqual(s3_asset.bucket_name, collected_s3_asset.bucket_name)

    def test_shallow_clone_image_asset(self):
        image_asset = ImageAsset()
        collected_image_asset = ImageAsset(
            source_local_image="source_local_image",
            target="target",
            build_args={"foo": "bar"},
            docker_file_name="Dockerfile",
            image_tag="tag",
            registry="registry",
            repository_name="repo",
        )
        collected_assets = {"id": collected_image_asset}
        _shallow_clone_asset(image_asset, "id", collected_assets)
        self.assertNotEqual(image_asset, collected_image_asset)
        self.assertEqual(image_asset.source_local_image, collected_image_asset.source_local_image)
        self.assertEqual(image_asset.target, collected_image_asset.target)
        self.assertEqual(image_asset.build_args, collected_image_asset.build_args)
        self.assertEqual(image_asset.docker_file_name, collected_image_asset.docker_file_name)
        self.assertEqual(image_asset.image_tag, collected_image_asset.image_tag)
        self.assertEqual(image_asset.registry, collected_image_asset.registry)
        self.assertEqual(image_asset.repository_name, collected_image_asset.repository_name)


class TestUpdateAssetParamsDefaultValues(TestCase):
    def test_update_asset_params_default_values(self):
        asset = S3Asset(
            asset_id="asset",
            bucket_name="bucket",
            object_key="key",
            object_version="version",
            extra_details={
                "assetParameters": {
                    "s3BucketParameter": "xxx",
                    "s3KeyParameter": "yyy",
                    "artifactHashParameter": "zzz",
                }
            },
        )

        parameters = DictSection("Parameters")
        parameters["xxx"] = {"Type": "String"}
        parameters["yyy"] = {"Type": "String"}
        parameters["zzz"] = {"Type": "String"}

        _update_asset_params_default_values(asset, parameters)
        self.assertIn("Default", parameters["xxx"])
        self.assertEqual(parameters["xxx"]["Default"], "bucket")
        self.assertIn("Default", parameters["yyy"])
        self.assertEqual(parameters["yyy"]["Default"], "key||version")
        self.assertIn("Default", parameters["zzz"])
        self.assertEqual(parameters["zzz"]["Default"], "asset")


class TestGetCdkExecutablePath(TestCase):
    @patch("platform.system", return_value="windows")
    @patch("shutil.which", return_value="cdk.exe")
    def test_get_cdk_executable_path_windows(self, which_mock, system_mock):
        executable_path = _get_cdk_executable_path()
        self.assertEqual(executable_path, "cdk.exe")

    @patch("platform.system", return_value="linux")
    @patch("shutil.which", return_value="cdk")
    def test_get_cdk_executable_path_non_windows(self, which_mock, system_mock):
        executable_path = _get_cdk_executable_path()
        self.assertEqual(executable_path, "cdk")

    @patch("platform.system", return_value="linux")
    @patch("shutil.which", return_value=None)
    def test_get_cdk_executable_path_not_found(self, which_mock, system_mock):
        with self.assertRaises(CdkToolkitNotInstalledError):
            _get_cdk_executable_path()


class TestUpdateBuiltArtifacts(TestCase):
    def setUp(self):
        self.manifest_dict = {
            "artifacts": {
                "root-stack-1": {
                    "metadata": {
                        "/root-stack-1": [
                            {
                                "type": "aws:cdk:asset",
                                "data": {
                                    "id": "asset1",
                                    "packaging": "zip",
                                    "path": "original_path",
                                },
                            }
                        ]
                    }
                },
                "root-stack-2": {},
            }
        }
        self.updated_manifest = {
            "artifacts": {
                "root-stack-1": {
                    "metadata": {
                        "/root-stack-1": [
                            {
                                "type": "aws:cdk:asset",
                                "data": {
                                    "id": "asset1",
                                    "packaging": "zip",
                                    "path": "updated_source_path",
                                },
                            }
                        ]
                    }
                },
                "root-stack-2": {},
            }
        }
        self.assets = {"root-stack-1": {"asset1": S3Asset(updated_source_path="updated_source_path")}}
        self.mock_open = mock_open()
        self.collect_project_assets_mock_return_value = (self.assets, ["root-stack-1"])

    @patch("os.path.join", return_value="path/to/file")
    @patch("json.loads")
    @patch("json.dumps")
    @patch("samcli.lib.iac.cdk.plugin._collect_project_assets")
    def test_update_built_artifacts(
        self, collect_project_assets_mock, json_dumps_mock, json_loads_mock, os_path_join_mock
    ):
        json_loads_mock.return_value = self.manifest_dict
        with patch("samcli.lib.iac.cdk.plugin.open", self.mock_open):
            project = Project(stacks=[])
            collect_project_assets_mock.return_value = self.collect_project_assets_mock_return_value
            _update_built_artifacts(project, "cloud_assembly_dir", "build_dir")
            json_dumps_mock.assert_called_once_with(self.updated_manifest, indent=4)
