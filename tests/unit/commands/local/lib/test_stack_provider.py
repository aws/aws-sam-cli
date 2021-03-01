import os
from unittest import TestCase
from unittest.mock import patch

from parameterized import parameterized

from samcli.commands._utils.resources import AWS_SERVERLESS_APPLICATION, AWS_CLOUDFORMATION_STACK
from samcli.lib.providers.provider import Stack
from samcli.lib.providers.sam_stack_provider import SamLocalStackProvider

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
            (AWS_SERVERLESS_APPLICATION, "Location", "./child.yaml", "child.yaml"),
            (AWS_CLOUDFORMATION_STACK, "TemplateURL", "./child.yaml", "child.yaml"),
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
        with patch.dict(os.environ, {SamLocalStackProvider.ENV_SAM_CLI_ENABLE_NESTED_STACK: "1"}):
            stacks = SamLocalStackProvider.get_stacks(
                self.template_file,
                "",
                "",
                parameter_overrides=None,
            )
        self.assertListEqual(
            stacks,
            [
                Stack("", "", self.template_file, {}, template),
                Stack("", "ChildStack", child_location_path, {}, LEAF_TEMPLATE),
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
        with patch.dict(os.environ, {SamLocalStackProvider.ENV_SAM_CLI_ENABLE_NESTED_STACK: ""}):
            stacks = SamLocalStackProvider.get_stacks(
                self.template_file,
                "",
                "",
                parameter_overrides=None,
            )
        self.assertListEqual(
            stacks,
            [
                Stack("", "", self.template_file, {}, template),
            ],
        )

    def test_sam_deep_nested_stack(self):
        child_template_file = "child.yaml"
        grand_child_template_file = "grand-child.yaml"
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
        with patch.dict(os.environ, {SamLocalStackProvider.ENV_SAM_CLI_ENABLE_NESTED_STACK: "1"}):
            stacks = SamLocalStackProvider.get_stacks(
                self.template_file,
                "",
                "",
                parameter_overrides=None,
            )
        self.assertListEqual(
            stacks,
            [
                Stack("", "", self.template_file, {}, template),
                Stack("", "ChildStack", child_template_file, {}, child_template),
                Stack("ChildStack", "GrandChildStack", grand_child_template_file, {}, LEAF_TEMPLATE),
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
        with patch.dict(os.environ, {SamLocalStackProvider.ENV_SAM_CLI_ENABLE_NESTED_STACK: "1"}):
            stacks = SamLocalStackProvider.get_stacks(
                self.template_file,
                "",
                "",
                parameter_overrides=None,
            )
        self.assertListEqual(
            stacks,
            [
                Stack("", "", self.template_file, {}, template),
            ],
        )

    @parameterized.expand(
        [
            (AWS_SERVERLESS_APPLICATION, "Location", "./child.yaml", os.path.join("somedir", "child.yaml")),
            (AWS_SERVERLESS_APPLICATION, "Location", "child.yaml", os.path.join("somedir", "child.yaml")),
            (AWS_CLOUDFORMATION_STACK, "TemplateURL", "./child.yaml", os.path.join("somedir", "child.yaml")),
            (AWS_CLOUDFORMATION_STACK, "TemplateURL", "child.yaml", os.path.join("somedir", "child.yaml")),
            (AWS_SERVERLESS_APPLICATION, "Location", "file:///child.yaml", "/child.yaml"),
            (AWS_CLOUDFORMATION_STACK, "TemplateURL", "file:///child.yaml", "/child.yaml"),
        ]
    )
    def test_sam_nested_stack_template_path_can_be_resolved_if_root_template_is_not_in_working_dir(
        self, resource_type, location_property_name, child_location, child_location_path
    ):
        template_file = "somedir/template.yaml"
        template = {
            "Resources": {
                "ChildStack": {
                    "Type": resource_type,
                    "Properties": {location_property_name: child_location},
                }
            }
        }
        self.get_template_data_mock.side_effect = lambda t: {
            template_file: template,
            child_location_path: LEAF_TEMPLATE,
        }.get(t)
        with patch.dict(os.environ, {SamLocalStackProvider.ENV_SAM_CLI_ENABLE_NESTED_STACK: "1"}):
            stacks = SamLocalStackProvider.get_stacks(
                template_file,
                "",
                "",
                parameter_overrides=None,
            )
        self.assertListEqual(
            stacks,
            [
                Stack("", "", template_file, {}, template),
                Stack("", "ChildStack", child_location_path, {}, LEAF_TEMPLATE),
            ],
        )

    @parameterized.expand(
        [
            (AWS_SERVERLESS_APPLICATION, "Location", "./child.yaml", os.path.join("somedir", "child.yaml")),
            (AWS_SERVERLESS_APPLICATION, "Location", "child.yaml", os.path.join("somedir", "child.yaml")),
            (AWS_CLOUDFORMATION_STACK, "TemplateURL", "./child.yaml", os.path.join("somedir", "child.yaml")),
            (AWS_CLOUDFORMATION_STACK, "TemplateURL", "child.yaml", os.path.join("somedir", "child.yaml")),
            (AWS_SERVERLESS_APPLICATION, "Location", "file:///child.yaml", "/child.yaml"),
            (AWS_CLOUDFORMATION_STACK, "TemplateURL", "file:///child.yaml", "/child.yaml"),
        ]
    )
    def test_global_parameter_overrides_can_be_passed_to_child_stacks(
        self, resource_type, location_property_name, child_location, child_location_path
    ):
        template_file = "somedir/template.yaml"
        template = {
            "Resources": {
                "ChildStack": {
                    "Type": resource_type,
                    "Properties": {location_property_name: child_location},
                }
            }
        }
        self.get_template_data_mock.side_effect = lambda t: {
            template_file: template,
            child_location_path: LEAF_TEMPLATE,
        }.get(t)

        global_parameter_overrides = {"AWS::Region": "custom_region"}

        with patch.dict(os.environ, {SamLocalStackProvider.ENV_SAM_CLI_ENABLE_NESTED_STACK: "1"}):
            stacks = SamLocalStackProvider.get_stacks(
                template_file, "", "", parameter_overrides=None, global_parameter_overrides=global_parameter_overrides
            )
        self.assertListEqual(
            stacks,
            [
                Stack("", "", template_file, global_parameter_overrides, template),
                Stack("", "ChildStack", child_location_path, global_parameter_overrides, LEAF_TEMPLATE),
            ],
        )
