import os
import tempfile
from pathlib import Path
from unittest import TestCase, skipIf

from parameterized import parameterized

from samcli.commands._utils.resources import AWS_SERVERLESS_APPLICATION, AWS_CLOUDFORMATION_STACK
from samcli.lib.iac.interface import Stack as IacStack
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
        parent_stack = IacStack(origin_dir=".")
        parent_stack.update(
            {
                "Resources": {
                    "ChildStack": {
                        "Type": resource_type,
                        "Properties": {location_property_name: child_location},
                    }
                }
            }
        )
        child_stack = IacStack(name="ChildStack", origin_dir=parent_stack.origin_dir, is_nested=True)
        child_stack.update(LEAF_TEMPLATE)
        parent_stack["Resources"]["ChildStack"].nested_stack = child_stack
        stacks, remote_stack_full_paths = SamLocalStackProvider.get_stacks(
            [parent_stack],
            "",
            "",
            parameter_overrides=None,
        )
        self.assertListEqual(
            stacks,
            [
                Stack("", "", "", {}, parent_stack),
                Stack("", "ChildStack", "ChildStack", {}, child_stack),
            ],
        )
        self.assertFalse(remote_stack_full_paths)

    def test_sam_deep_nested_stack(self):
        child_template_file = "child.yaml"
        grand_child_template_file = "grand-child.yaml"

        parent_stack = IacStack(origin_dir=".")
        parent_stack.update(
            {
                "Resources": {
                    "ChildStack": {
                        "Type": AWS_SERVERLESS_APPLICATION,
                        "Properties": {"Location": child_template_file},
                    }
                }
            }
        )

        child_stack = IacStack(name="ChildStack", origin_dir=parent_stack.origin_dir, is_nested=True)
        child_stack.update(
            {
                "Resources": {
                    "GrandChildStack": {
                        "Type": AWS_SERVERLESS_APPLICATION,
                        "Properties": {"Location": grand_child_template_file},
                    }
                }
            }
        )
        parent_stack["Resources"]["ChildStack"].nested_stack = child_stack

        grand_stack = IacStack(name="GrandChildStack", origin_dir=child_stack.origin_dir, is_nested=True)
        grand_stack.update(LEAF_TEMPLATE)
        child_stack["Resources"]["GrandChildStack"].nested_stack = grand_stack

        stacks, remote_stack_full_paths = SamLocalStackProvider.get_stacks(
            [parent_stack],
            "",
            "",
            parameter_overrides=None,
        )
        self.assertListEqual(
            stacks,
            [
                Stack("", "", "", {}, parent_stack),
                Stack("", "ChildStack", "ChildStack", {}, child_stack),
                Stack("ChildStack", "GrandChildStack", "GrandChildStack", {}, grand_stack),
            ],
        )
        self.assertFalse(remote_stack_full_paths)

    @parameterized.expand([(AWS_SERVERLESS_APPLICATION, "Location"), (AWS_CLOUDFORMATION_STACK, "TemplateURL")])
    def test_remote_stack_is_skipped(self, resource_type, location_property_name):
        parent_stack = IacStack(origin_dir=".")
        parent_stack.update(
            {
                "Resources": {
                    "ChildStack": {
                        "Type": resource_type,
                        "Properties": {location_property_name: "s3://bucket/key"},
                    }
                }
            }
        )

        stacks, remote_stack_full_paths = SamLocalStackProvider.get_stacks(
            [parent_stack],
            "",
            "",
            parameter_overrides=None,
        )
        self.assertListEqual(
            stacks,
            [
                Stack("", "", "", {}, parent_stack),
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
        parent_stack = IacStack(origin_dir="somedir")
        parent_stack.update(
            {
                "Resources": {
                    "ChildStack": {
                        "Type": resource_type,
                        "Properties": {location_property_name: child_location},
                    }
                }
            }
        )
        child_stack = IacStack(name="ChildStack", origin_dir=parent_stack.origin_dir, is_nested=True)
        child_stack.update(LEAF_TEMPLATE)
        parent_stack["Resources"]["ChildStack"].nested_stack = child_stack
        stacks, remote_stack_full_paths = SamLocalStackProvider.get_stacks(
            [parent_stack],
            "",
            "",
            parameter_overrides=None,
        )
        self.assertListEqual(
            stacks,
            [
                Stack("", "", "", {}, parent_stack),
                Stack("", "ChildStack", "ChildStack", {}, child_stack),
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
        parent_stack = IacStack(origin_dir="somedir")
        parent_stack.update(
            {
                "Resources": {
                    "ChildStack": {
                        "Type": resource_type,
                        "Properties": {location_property_name: child_location},
                    }
                }
            }
        )
        child_stack = IacStack(name="ChildStack", origin_dir=parent_stack.origin_dir, is_nested=True)
        child_stack.update(LEAF_TEMPLATE)
        parent_stack["Resources"]["ChildStack"].nested_stack = child_stack

        global_parameter_overrides = {"AWS::Region": "custom_region"}

        stacks, remote_stack_full_paths = SamLocalStackProvider.get_stacks(
            [parent_stack], "", "", parameter_overrides=None, global_parameter_overrides=global_parameter_overrides
        )
        self.assertListEqual(
            stacks,
            [
                Stack("", "", "", global_parameter_overrides, parent_stack),
                Stack("", "ChildStack", "ChildStack", global_parameter_overrides, LEAF_TEMPLATE),
            ],
        )
        self.assertFalse(remote_stack_full_paths)

    @parameterized.expand(
        [
            ("/path", "./code", "/path/code"),
            ("/path", "code", "/path/code"),
            ("/path", "/code", "/code"),
            ("path", "./code", "path/code"),
            ("path", "code", "path/code"),
            ("path", "/code", "/code"),
            ("./path", "./code", "path/code"),
            ("./path", "code", "path/code"),
            ("./path", "/code", "/code"),
            ("./path", "../../code", "../code"),
            ("./path", "code/../code", "path/code"),
            ("./path", "/code", "/code"),
        ]
    )
    @skipIf(IS_WINDOWS, "only run test_normalize_resource_path_windows_* on Windows")
    def test_normalize_resource_path_poxis(self, stack_location_directory, path, normalized_path):
        self.assertEqual(SamLocalStackProvider.normalize_resource_path(stack_location_directory, path), normalized_path)

    @parameterized.expand(
        [
            ("C:\\path", ".\\code", "C:\\path\\code"),
            ("C:\\path", "code", "C:\\path\\code"),
            ("C:\\pathl", "D:\\code", "D:\\code"),
            ("path", ".\\code", "path\\code"),
            ("path", "code", "path\\code"),
            ("path", "D:\\code", "D:\\code"),
            (".\\path", ".\\code", "path\\code"),
            (".\\path", "code", "path\\code"),
            (".\\path", "D:\\code", "D:\\code"),
            (".\\path", "..\\..\\code", "..\\code"),
            (".\\path", "code\\..\\code", "path\\code"),
            (".\\path", "D:\\code", "D:\\code"),
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

            os.symlink(os.path.join("..", "some", "path"), link1)
            os.symlink("link1", link2)

            self.assertEqual(
                SamLocalStackProvider.normalize_resource_path(link2, resource_path),
                expected,
            )
