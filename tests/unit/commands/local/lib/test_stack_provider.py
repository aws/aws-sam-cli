import os
from unittest import TestCase
from unittest.mock import patch

from parameterized import parameterized

from samcli.commands._utils.resources import AWS_SERVERLESS_APPLICATION, AWS_CLOUDFORMATION_STACK
from samcli.lib.providers.provider import LocalBuildableStack
from samcli.lib.providers.sam_stack_provider import SamBuildableStackProvider

# LEAF_TEMPLATE is a template without any nested application/stack in it
LEAF_TEMPLATE = {
    "Resources": {
        "AFunction": {
            "Type": "AWS::Serverless::Function",
            "Properties": {"CodeUri": "hi/", "Runtime": "python3.7"},
        }
    }
}


class TestSamBuildableStackProvider(TestCase):
    template_file = "template_file.yaml"

    def setUp(self):
        patcher = patch("samcli.lib.providers.sam_stack_provider.get_template_data")
        self.get_template_data_mock = patcher.start()
        self.addCleanup(patcher.stop)

    @parameterized.expand(
        [
            (AWS_SERVERLESS_APPLICATION, "Location", "./child.yaml", "./child.yaml"),
            (AWS_CLOUDFORMATION_STACK, "TemplateURL", "./child.yaml", "./child.yaml"),
            (AWS_SERVERLESS_APPLICATION, "Location", "file:///child.yaml", "/child.yaml"),
            (AWS_CLOUDFORMATION_STACK, "TemplateURL", "file:///child.yaml", "/child.yaml"),
        ]
    )
    def test_sam_nested_stack_should_be_extracted(
        self, resource_type, location_property_name, child_location, child_location_path
    ):
        template = {
            "Resources": {
                "ChildStack": {
                    "Type": resource_type,
                    "Properties": {location_property_name: child_location},
                }
            }
        }
        self.get_template_data_mock.side_effect = lambda t: {
            self.template_file: template,
            child_location_path: LEAF_TEMPLATE,
        }.get(t)
        with patch.dict(os.environ, {SamBuildableStackProvider.ENV_SAM_CLI_ENABLE_NESTED_STACK: "1"}):
            stacks = SamBuildableStackProvider.get_local_buildable_stacks(
                self.template_file,
                "",
                "",
                parameter_overrides=None,
            )
        self.assertListEqual(
            stacks,
            [
                LocalBuildableStack("", "", self.template_file, None, template),
                LocalBuildableStack("", "ChildStack", child_location_path, None, LEAF_TEMPLATE),
            ],
        )

    @parameterized.expand(
        [
            (AWS_SERVERLESS_APPLICATION, "Location", "./child.yaml", "./child.yaml"),
            (AWS_CLOUDFORMATION_STACK, "TemplateURL", "./child.yaml", "./child.yaml"),
            (AWS_SERVERLESS_APPLICATION, "Location", "file:///child.yaml", "/child.yaml"),
            (AWS_CLOUDFORMATION_STACK, "TemplateURL", "file:///child.yaml", "/child.yaml"),
        ]
    )
    def test_sam_nested_stack_should_not_be_extracted_when_recursive_is_disabled(
        self, resource_type, location_property_name, child_location, child_location_path
    ):
        template = {
            "Resources": {
                "ChildStack": {
                    "Type": resource_type,
                    "Properties": {location_property_name: child_location},
                }
            }
        }
        self.get_template_data_mock.side_effect = lambda t: {
            self.template_file: template,
            child_location_path: LEAF_TEMPLATE,
        }.get(t)
        with patch.dict(os.environ, {SamBuildableStackProvider.ENV_SAM_CLI_ENABLE_NESTED_STACK: ""}):
            stacks = SamBuildableStackProvider.get_local_buildable_stacks(
                self.template_file,
                "",
                "",
                parameter_overrides=None,
            )
        self.assertListEqual(
            stacks,
            [
                LocalBuildableStack("", "", self.template_file, None, template),
            ],
        )

    def test_sam_deep_nested_stack(self):
        child_template_file = "./child.yaml"
        grand_child_template_file = "./grand-child.yaml"
        template = {
            "Resources": {
                "ChildStack": {
                    "Type": AWS_SERVERLESS_APPLICATION,
                    "Properties": {"Location": child_template_file},
                }
            }
        }
        child_template = {
            "Resources": {
                "GrandChildStack": {
                    "Type": AWS_SERVERLESS_APPLICATION,
                    "Properties": {"Location": grand_child_template_file},
                }
            }
        }
        self.get_template_data_mock.side_effect = lambda t: {
            self.template_file: template,
            child_template_file: child_template,
            grand_child_template_file: LEAF_TEMPLATE,
        }.get(t)
        with patch.dict(os.environ, {SamBuildableStackProvider.ENV_SAM_CLI_ENABLE_NESTED_STACK: "1"}):
            stacks = SamBuildableStackProvider.get_local_buildable_stacks(
                self.template_file,
                "",
                "",
                parameter_overrides=None,
            )
        self.assertListEqual(
            stacks,
            [
                LocalBuildableStack("", "", self.template_file, None, template),
                LocalBuildableStack("", "ChildStack", child_template_file, None, child_template),
                LocalBuildableStack("ChildStack", "GrandChildStack", grand_child_template_file, None, LEAF_TEMPLATE),
            ],
        )

    @parameterized.expand([(AWS_SERVERLESS_APPLICATION, "Location"), (AWS_CLOUDFORMATION_STACK, "TemplateURL")])
    def test_remote_stack_is_skipped(self, resource_type, location_property_name):
        template = {
            "Resources": {
                "ChildStack": {
                    "Type": resource_type,
                    "Properties": {location_property_name: "s3://bucket/key"},
                }
            }
        }
        self.get_template_data_mock.side_effect = lambda t: {
            self.template_file: template,
        }.get(t)
        with patch.dict(os.environ, {SamBuildableStackProvider.ENV_SAM_CLI_ENABLE_NESTED_STACK: "1"}):
            stacks = SamBuildableStackProvider.get_local_buildable_stacks(
                self.template_file,
                "",
                "",
                parameter_overrides=None,
            )
        self.assertListEqual(
            stacks,
            [
                LocalBuildableStack("", "", self.template_file, None, template),
            ],
        )
