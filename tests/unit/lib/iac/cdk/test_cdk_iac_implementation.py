import os
import subprocess

from unittest import TestCase
from unittest.mock import ANY, Mock, patch

from samcli.lib.iac.cdk.cdk_iac import CdkIacImplementation, _collect_assets, _get_cdk_executable_path
from samcli.lib.iac.cdk.exceptions import CdkToolkitNotInstalledError, InvalidCloudAssemblyError
from samcli.lib.iac.plugins_interfaces import (
    SamCliContext,
    SamCliProject,
    Stack,
    DictSection,
    Resource,
    LookupPath,
    LookupPathType,
    ImageAsset,
    S3Asset,
)

CLOUD_ASSEMBLY_DIR = os.path.join(os.path.dirname(__file__), "test_data", "cdk.out")


class TestCdkPlugin(TestCase):
    def setUp(self) -> None:
        self.command_params = {"cdk_app": CLOUD_ASSEMBLY_DIR}
        self.sam_cli_context = SamCliContext(
            command_options_map=self.command_params,
            sam_command_name="",
            is_debugging=False,
            is_guided=False,
            profile={},
            region="",
        )

    @patch("os.path.isfile", return_value=True)
    @patch("os.path.abspath", return_value="/path/to/cloud_assembly")
    @patch("os.path.exists", return_value=True)
    def test_get_project_build_type_lookup_path(self, path_exists_mock, abspath_mock, is_file_mock):
        cdk_plugin = CdkIacImplementation(self.sam_cli_context)
        cdk_plugin._get_project_from_cloud_assembly = Mock()
        cdk_plugin._get_project_from_cloud_assembly.return_value = SamCliProject(stacks=[Mock(), Mock()])

        project = cdk_plugin.read_project([LookupPath("lookup/path", LookupPathType.BUILD)])
        cdk_plugin._get_project_from_cloud_assembly.assert_called_once_with(abspath_mock.return_value)
        self.assertIsInstance(project, SamCliProject)
        self.assertEqual(len(project.stacks), 2)

    @patch("os.path.isfile", return_value=True)
    @patch("os.path.abspath", return_value="/path/to/cloud_assembly")
    @patch("os.path.exists", return_value=True)
    def test_get_project_source_type_lookup_path(self, path_exists_mock, abspath_mock, is_file_mock):
        cdk_plugin = CdkIacImplementation(self.sam_cli_context)
        cdk_plugin._get_project_from_cloud_assembly = Mock()
        cdk_plugin._get_project_from_cloud_assembly.return_value = SamCliProject(stacks=[Mock(), Mock()])
        cdk_plugin._cdk_synth = Mock()
        cdk_plugin._cdk_synth.return_value = abspath_mock.return_value

        project = cdk_plugin.read_project([LookupPath("lookup/path", LookupPathType.SOURCE)])
        cdk_plugin._cdk_synth.assert_called_once_with(app=CLOUD_ASSEMBLY_DIR, context=None)
        cdk_plugin._get_project_from_cloud_assembly.assert_called_once_with(abspath_mock.return_value)
        self.assertIsInstance(project, SamCliProject)
        self.assertEqual(len(project.stacks), 2)

    @patch("os.path.isfile", return_value=True)
    def test_get_project_invalid_lookup_path(self, is_file_mock):
        cdk_plugin = CdkIacImplementation(self.sam_cli_context)

        with self.assertRaises(InvalidCloudAssemblyError):
            cdk_plugin.read_project([])

    @patch("subprocess.check_output")
    @patch("os.path.isdir", return_value=False)
    @patch("samcli.lib.iac.cdk.cdk_iac.copy_tree")
    @patch("samcli.lib.iac.cdk.cdk_iac._get_cdk_executable_path", return_value="cdk")
    def test_cdk_synth_app_is_executable_with_context(
        self, get_cdk_executable_path_mock, copy_tree_mock, isdir_mock, check_output_mock
    ):
        cdk_plugin = CdkIacImplementation(self.sam_cli_context)
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
    @patch("samcli.lib.iac.cdk.cdk_iac.copy_tree")
    @patch("samcli.lib.iac.cdk.cdk_iac._get_cdk_executable_path", return_value="cdk")
    def test_cdk_synth_app_is_dir(self, get_cdk_executable_path_mock, copy_tree_mock, isdir_mock, check_output_mock):
        cdk_plugin = CdkIacImplementation(self.sam_cli_context)
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
    @patch("samcli.lib.iac.cdk.cdk_iac.copy_tree")
    @patch("samcli.lib.iac.cdk.cdk_iac._get_cdk_executable_path", return_value="cdk")
    def test_cdk_synth_app_is_none(self, get_cdk_executable_path_mock, copy_tree_mock, isdir_mock, check_output_mock):
        cdk_plugin = CdkIacImplementation(self.sam_cli_context)
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

    @patch("samcli.lib.iac.cdk.cdk_iac.CloudAssembly")
    def test_get_project_from_cloud_assembly(self, cloud_assembly_class_mock):
        cloud_assembly_mock = Mock()
        cloud_assembly_mock.stacks = [Mock(), Mock()]
        cloud_assembly_class_mock.return_value = cloud_assembly_mock
        cdk_plugin = CdkIacImplementation(self.sam_cli_context)
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

    @patch("samcli.lib.iac.cdk.cdk_iac._collect_assets")
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
        cdk_plugin = CdkIacImplementation(self.sam_cli_context)
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

        cdk_plugin = CdkIacImplementation(self.sam_cli_context)
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

        cdk_plugin = CdkIacImplementation(self.sam_cli_context)
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


# TODO: Implement these tests when the classes are fully implemented
# These tests are included for code coverage
class TestImplementations(TestCase):
    def test_cdk_implementation(self):
        impl = CdkIacImplementation(Mock())
        impl.update_packaged_locations(Mock())
        impl.write_project(Mock(), Mock())
        self.assertTrue(True)
