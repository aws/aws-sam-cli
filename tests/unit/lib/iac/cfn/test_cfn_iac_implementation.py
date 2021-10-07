import copy
import os
from unittest import TestCase
from unittest.mock import patch, Mock, ANY

from samcli.commands._utils.template import TemplateFormat
from samcli.commands.validate.lib.exceptions import InvalidSamDocumentException
from samcli.lib.iac.cfn.cfn_iac import CfnIacImplementation, _write_stack, TEMPLATE_BUILD_PATH_KEY
from samcli.lib.iac.plugins_interfaces import (
    SamCliContext,
    SamCliProject,
    Stack,
    DictSectionItem,
    DictSection,
    Resource,
    S3Asset,
    ImageAsset,
)

GENERIC_CFN_TEMPLATE = {
    "Resources": {"Lambda": {"Type": "AWS::Serverless::Function"}},
    "Parameters": {
        "Param1": {"Type": "String", "Default": "foo"},
    },
    "OtherMapping": {},
    "OtherKey": "other",
}

TEST_DATA_DIR = os.path.join(os.path.dirname(__file__), "test_data")


class TestCfnPlugin(TestCase):
    def setUp(self) -> None:
        self.command_params = {"template_file": "/path/to/template"}
        self.sam_cli_context = SamCliContext(
            command_options_map=self.command_params,
            sam_command_name="",
            is_debugging=False,
            is_guided=False,
            profile={},
            region="",
        )

    @patch("samcli.lib.iac.cfn.cfn_iac.get_template_data")
    def test_read_project(self, mock_get_template_data):
        mock_get_template_data.return_value = GENERIC_CFN_TEMPLATE
        plugin = CfnIacImplementation(self.sam_cli_context)
        project = plugin.read_project([])
        resource_type = project.stacks[0].sections.get("Resources").section_items[0].body.get("Type")
        self.assertIsInstance(project, SamCliProject)
        self.assertEqual(len(project.stacks[0].sections), 4)
        self.assertEqual(resource_type, "AWS::Serverless::Function")

    @patch("samcli.lib.iac.cfn.cfn_iac.get_template_data")
    def test_build_stack(self, mock_get_template_data):
        mock_get_template_data.return_value = GENERIC_CFN_TEMPLATE
        plugin = CfnIacImplementation(self.sam_cli_context)
        stack = plugin._build_stack("/path/to/template", False, "test_stack")
        self.assertIsInstance(stack, Stack)
        self.assertEqual(stack.stack_id, "test_stack")
        self.assertEqual(stack.name, "test_stack")
        self.assertFalse(stack.is_nested, False)
        self.assertIn("Param1", stack.get("Parameters"))

    def test_build_nested_stack(self):
        template_path = os.path.join(TEST_DATA_DIR, "nested_stack.yaml")
        plugin = CfnIacImplementation(self.sam_cli_context)
        stack = plugin._build_stack(template_path, False, "test_stack")
        nested_stack = stack.sections.get("Resources").section_items[0].nested_stack
        nested_stack_resource_type = nested_stack.sections.get("Resources").section_items[0].body.get("Type")
        self.assertIsInstance(stack, Stack)
        self.assertFalse(stack.is_nested)
        self.assertEqual(stack.stack_id, "test_stack")
        self.assertEqual(stack.name, "test_stack")
        self.assertIsInstance(nested_stack, Stack)
        self.assertTrue(nested_stack.is_nested)
        self.assertEqual(nested_stack.name, "SubApp")
        self.assertEqual(nested_stack_resource_type, "AWS::Serverless::Function")

    @patch("samcli.lib.iac.cfn.cfn_iac.get_template_data")
    def test_build_with_metadata_section(self, mock_get_template_data):
        mock_get_template_data.return_value = {
            "Metadata": {
                "AWS::ServerlessRepo::Application": {
                    "Name": "my-app",
                    "LicenseUrl": "./LICENSE.txt",
                }
            },
            "Resources": {"Lambda": {"Type": "AWS::Serverless::Function"}},
        }

        plugin = CfnIacImplementation(self.sam_cli_context)
        stack = plugin._build_stack("/path/to/template", False, "test_stack")
        metadata = stack.sections.get("Metadata").section_items[0]
        metadata_assets = metadata.assets
        self.assertIsInstance(metadata, DictSectionItem)
        self.assertEqual(metadata.item_id, "AWS::ServerlessRepo::Application")
        self.assertEqual(len(metadata_assets), 2)
        self.assertEqual(metadata_assets[0].source_path, "./LICENSE.txt")
        self.assertEqual(metadata.body.get("Name"), "my-app")
        self.assertEqual(metadata.body.get("LicenseUrl"), "./LICENSE.txt")

    @patch("samcli.lib.iac.cfn.cfn_iac.get_template_data")
    def test_build_stack_resolves_intrinsics(self, mock_get_template_data):
        mock_get_template_data.return_value = {
            "Parameters": {
                "MyStageName": {"Type": "String", "Default": "Production"},
                "Endpoint": {"Type": "String", "Default": "https://some-domain/endpoint"},
            },
            "Resources": {
                "GetHtmlApi": {
                    "Type": "AWS::Serverless::Api",
                    "Properties": {
                        "Name": "MyGetApi",
                        "StageName": {"Ref": "MyStageName"},
                        "DefinitionUri": {"Bucket": "sam-demo-bucket", "Key": "webpage_swagger.json"},
                        "Variables": {"EndpointUri": {"Ref": "Endpoint"}, "EndpointUri2": "http://example.com"},
                    },
                }
            },
        }
        plugin = CfnIacImplementation(self.sam_cli_context)
        stack = plugin._build_stack("/path/to/template", False, "test_stack")
        resource = (stack.sections.get("Resources")).section_items[0]
        endpoint_uri = resource.body.get("Properties").get("Variables").get("EndpointUri")
        stage_name = resource.body.get("Properties").get("StageName")
        self.assertIsInstance(stack, Stack)
        self.assertEqual(endpoint_uri, "https://some-domain/endpoint")
        self.assertEqual(stage_name, "Production")

    @patch("samcli.lib.iac.cfn.cfn_iac.get_template_data")
    def test_build_stack_no_resources(self, mock_get_template_data):
        mock_get_template_data.return_value = {
            "Resources": {},
            "Parameters": {
                "Param1": {"Type": "String", "Default": "foo"},
            },
            "OtherMapping": {},
            "OtherKey": "other",
        }
        plugin = CfnIacImplementation(self.sam_cli_context)
        plugin._build_resources_section = Mock()
        with self.assertRaises(InvalidSamDocumentException) as ctx:
            plugin._build_stack("/path/to/template", False, "test_stack")
        self.assertIn("'Resources' section is required", str(ctx.exception))

    @patch("samcli.lib.iac.cfn.cfn_iac.get_template_data")
    def test_build_stack_parameter_overrides(self, mock_get_template_data):
        command_params = {
            "template_file": "/path/to/template",
            "parameter_overrides": {"CodeUri": "/new/path/to/code"},
            "global_parameter_overrides": {"AWS::Region": "us-east-2"},
        }
        sam_cli_context = SamCliContext(
            command_options_map=command_params,
            sam_command_name="",
            is_debugging=False,
            is_guided=False,
            profile={},
            region="",
        )
        mock_get_template_data.return_value = {
            "Parameters": {
                "CodeUri": {"Type": "String", "Default": "/path/to/code"},
            },
            "Resources": {
                "GetHtmlApi": {
                    "Type": "AWS::Serverless::Function",
                    "Properties": {
                        "CodeUri": {"Ref": "CodeUri"},
                        "Environment": {"Variables": {"Region": {"Ref": "AWS::Region"}}},
                    },
                }
            },
        }
        cdk_plugin = CfnIacImplementation(sam_cli_context)
        stack = cdk_plugin._build_stack("/path/to/template", False, "test_stack")
        resource = (stack.sections.get("Resources")).section_items[0]
        code_uri = resource.body.get("Properties").get("CodeUri")
        region = resource.body.get("Properties").get("Environment").get("Variables").get("Region")
        self.assertIsInstance(stack, Stack)
        self.assertEqual(code_uri, "/new/path/to/code")
        self.assertEqual(region, "us-east-2")


class TestWriteStack(TestCase):
    def setUp(self):
        self.original_func = _write_stack

    @patch("samcli.lib.iac.cfn.cfn_iac.move_template")
    def test_write_stack(self, move_template_mock):
        stack = Stack(stack_id="test_stack")
        stack["Resources"] = DictSection("Resources")
        stack.extra_details["template_path"] = "template_path"
        resource = Resource(
            "Function1",
            body={
                "Type": "AWS::Lambda::Function",
                "Properties": {},
            },
        )
        stack["Resources"]["Function1"] = resource
        s3_asset = S3Asset(
            asset_id="id",
            updated_source_path="updated_source_path",
        )
        resource.assets.append(s3_asset)
        build_location = "build_dir/test_stack/template.yaml"
        _write_stack(stack, "build_dir")
        move_template_mock.assert_called_once_with("template_path", build_location, stack)
        self.assertEqual(stack.extra_details[TEMPLATE_BUILD_PATH_KEY], build_location)

    @patch("samcli.lib.iac.cfn.cfn_iac.move_template")
    @patch("samcli.lib.iac.cfn.cfn_iac._write_stack")
    def test_write_stack_s3_asset_nested_stack(self, write_stack_mock, move_template_mock):
        stack = Stack(stack_id="test_stack")
        stack["Resources"] = DictSection("Resources")
        stack.extra_details["template_path"] = "template_path"
        resource = Resource(
            "NestedStack",
            body={
                "Type": "AWS::Serverless::Application",
                "Properties": {},
            },
        )
        stack["Resources"]["Function1"] = resource
        s3_asset = S3Asset(
            asset_id="id",
            updated_source_path="updated_source_path",
            source_property="Location",
        )
        resource.assets.append(s3_asset)
        resource.nested_stack = Stack(
            sections={"Resources": {}}, extra_details={"template_build_path": "hello.nested-stack.json"}
        )

        build_location = "build_dir/test_stack/template.yaml"
        self.original_func(stack, "build_dir")
        self.assertEqual(s3_asset.updated_source_path, "hello.nested-stack.json")
        write_stack_mock.assert_called_once_with(resource.nested_stack, "build_dir/test_stack")
        move_template_mock.assert_called_once_with("template_path", build_location, stack)
