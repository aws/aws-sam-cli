import os
import tempfile
from pathlib import Path
from unittest import TestCase, skipIf
from unittest.mock import patch, Mock

from parameterized import parameterized

from samcli.lib.utils.resources import AWS_SERVERLESS_APPLICATION, AWS_CLOUDFORMATION_STACK
from samcli.lib.providers.provider import Stack
from samcli.lib.providers.sam_stack_provider import SamLocalStackProvider

# LEAF_TEMPLATE is a template without any nested application/stack in it
from tests.testing_utils import IS_WINDOWS

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
            (
                AWS_SERVERLESS_APPLICATION,
                "Location",
                "./child.yaml",
                "child.yaml",
                {},
                "ChildStack",
            ),
            (
                AWS_CLOUDFORMATION_STACK,
                "TemplateURL",
                "./child.yaml",
                "child.yaml",
                {},
                "ChildStack",
            ),
            (
                AWS_SERVERLESS_APPLICATION,
                "Location",
                "file:///child.yaml",
                "/child.yaml",
                {},
                "ChildStack",
            ),
            (
                AWS_CLOUDFORMATION_STACK,
                "TemplateURL",
                "file:///child.yaml",
                "/child.yaml",
                {},
                "ChildStack",
            ),
            (
                AWS_SERVERLESS_APPLICATION,
                "Location",
                "./child.yaml",
                "child.yaml",
                {"SamResourceId": "ChildStackId-x"},
                "ChildStackId-x",
            ),
            (
                AWS_CLOUDFORMATION_STACK,
                "TemplateURL",
                "./child.yaml",
                "child.yaml",
                {"SamResourceId": "ChildStackId-x"},
                "ChildStackId-x",
            ),
            (
                AWS_SERVERLESS_APPLICATION,
                "Location",
                "file:///child.yaml",
                "/child.yaml",
                {"SamResourceId": "ChildStackId-x"},
                "ChildStackId-x",
            ),
            (
                AWS_CLOUDFORMATION_STACK,
                "TemplateURL",
                "file:///child.yaml",
                "/child.yaml",
                {"SamResourceId": "ChildStackId-x"},
                "ChildStackId-x",
            ),
        ]
    )
    def test_sam_nested_stack_should_be_extracted(
        self, resource_type, location_property_name, child_location, child_location_path, metadata, expected_stack_id
    ):
        template = {
            "Resources": {
                "ChildStack": {
                    "Type": resource_type,
                    "Properties": {location_property_name: child_location},
                    "Metadata": metadata,
                }
            }
        }
        self.get_template_data_mock.side_effect = lambda t: {
            self.template_file: template,
            child_location_path: LEAF_TEMPLATE,
        }.get(t)
        stacks, remote_stack_full_paths = SamLocalStackProvider.get_stacks(
            self.template_file,
            "",
            "",
            parameter_overrides=None,
        )
        self.assertListEqual(
            stacks,
            [
                Stack("", "", self.template_file, {}, template),
                Stack("", "ChildStack", child_location_path, {}, LEAF_TEMPLATE, {"SamResourceId": expected_stack_id}),
            ],
        )
        self.assertFalse(remote_stack_full_paths)

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
        stacks, remote_stack_full_paths = SamLocalStackProvider.get_stacks(
            self.template_file,
            "",
            "",
            parameter_overrides=None,
        )
        self.assertListEqual(
            stacks,
            [
                Stack("", "", self.template_file, {}, template),
                Stack("", "ChildStack", child_template_file, {}, child_template, {"SamResourceId": "ChildStack"}),
                Stack(
                    "ChildStack",
                    "GrandChildStack",
                    grand_child_template_file,
                    {},
                    LEAF_TEMPLATE,
                    {"SamResourceId": "GrandChildStack"},
                ),
            ],
        )
        self.assertFalse(remote_stack_full_paths)

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
        stacks, remote_stack_full_paths = SamLocalStackProvider.get_stacks(
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
        self.assertEqual(remote_stack_full_paths, ["ChildStack"])

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
        stacks, remote_stack_full_paths = SamLocalStackProvider.get_stacks(
            template_file,
            "",
            "",
            parameter_overrides=None,
        )
        self.assertListEqual(
            stacks,
            [
                Stack("", "", template_file, {}, template),
                Stack("", "ChildStack", child_location_path, {}, LEAF_TEMPLATE, {"SamResourceId": "ChildStack"}),
            ],
        )
        self.assertFalse(remote_stack_full_paths)

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

        stacks, remote_stack_full_paths = SamLocalStackProvider.get_stacks(
            template_file, "", "", parameter_overrides=None, global_parameter_overrides=global_parameter_overrides
        )
        self.assertListEqual(
            stacks,
            [
                Stack("", "", template_file, global_parameter_overrides, template),
                Stack(
                    "",
                    "ChildStack",
                    child_location_path,
                    global_parameter_overrides,
                    LEAF_TEMPLATE,
                    {"SamResourceId": "ChildStack"},
                ),
            ],
        )
        self.assertFalse(remote_stack_full_paths)

    @parameterized.expand(
        [
            ("/path/template.yaml", "./code", "/path/code"),
            ("/path/template.yaml", "code", "/path/code"),
            ("/path/template.yaml", "/code", "/code"),
            ("path/template.yaml", "./code", "path/code"),
            ("path/template.yaml", "code", "path/code"),
            ("path/template.yaml", "/code", "/code"),
            ("./path/template.yaml", "./code", "path/code"),
            ("./path/template.yaml", "code", "path/code"),
            ("./path/template.yaml", "/code", "/code"),
            ("./path/template.yaml", "../../code", "../code"),
            ("./path/template.yaml", "code/../code", "path/code"),
            ("./path/template.yaml", "/code", "/code"),
        ]
    )
    @skipIf(IS_WINDOWS, "only run test_normalize_resource_path_windows_* on Windows")
    def test_normalize_resource_path_poxis(self, stack_location, path, normalized_path):
        self.assertEqual(SamLocalStackProvider.normalize_resource_path(stack_location, path), normalized_path)

    @parameterized.expand(
        [
            ("C:\\path\\template.yaml", ".\\code", "C:\\path\\code"),
            ("C:\\path\\template.yaml", "code", "C:\\path\\code"),
            ("C:\\path\\template.yaml", "D:\\code", "D:\\code"),
            ("path\\template.yaml", ".\\code", "path\\code"),
            ("path\\template.yaml", "code", "path\\code"),
            ("path\\template.yaml", "D:\\code", "D:\\code"),
            (".\\path\\template.yaml", ".\\code", "path\\code"),
            (".\\path\\template.yaml", "code", "path\\code"),
            (".\\path\\template.yaml", "D:\\code", "D:\\code"),
            (".\\path\\template.yaml", "..\\..\\code", "..\\code"),
            (".\\path\\template.yaml", "code\\..\\code", "path\\code"),
            (".\\path\\template.yaml", "D:\\code", "D:\\code"),
        ]
    )
    @skipIf(not IS_WINDOWS, "skip test_normalize_resource_path_windows_* on non-Windows system")
    def test_normalize_resource_path_windows(self, stack_location, path, normalized_path):
        self.assertEqual(SamLocalStackProvider.normalize_resource_path(stack_location, path), normalized_path)

    @skipIf(IS_WINDOWS, "symlink is not resolved consistently on windows")
    def test_normalize_resource_path_symlink(self):
        """
        template: tmp_dir/some/path/template.yaml
        link1 (tmp_dir/symlinks/link1) -> ../some/path/template.yaml
        link2 (tmp_dir/symlinks/link1) -> tmp_dir/symlinks/link1
        resource_path (tmp_dir/some/path/src), raw path is "src"
        The final expected value is the actual value of resource_path, which is tmp_dir/some/path/src

        Skip the test on windows, due to symlink is not resolved consistently on Python:
        https://stackoverflow.com/questions/43333640/python-os-path-realpath-for-symlink-in-windows
        """
        with tempfile.TemporaryDirectory() as tmp_dir:
            Path(tmp_dir, "some", "path").mkdir(parents=True)
            Path(tmp_dir, "symlinks").mkdir(parents=True)

            link1 = os.path.join(tmp_dir, "symlinks", "link1")
            link2 = os.path.join(tmp_dir, "symlinks", "link2")

            resource_path = "src"

            # on mac, tmp_dir itself could be a symlink
            real_tmp_dir = os.path.realpath(tmp_dir)
            # SamLocalStackProvider.normalize_resource_path() always returns a relative path.
            # so expected is converted to relative path
            expected = os.path.relpath(os.path.join(real_tmp_dir, os.path.join("some", "path", "src")))

            os.symlink(os.path.join("..", "some", "path", "template.yaml"), link1)
            os.symlink("link1", link2)

            self.assertEqual(
                SamLocalStackProvider.normalize_resource_path(link2, resource_path),
                expected,
            )
